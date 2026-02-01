from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import smtplib
from email.message import EmailMessage







app = Flask(__name__)
app.secret_key = "smart_bus_secret"
COLLEGE_LAT = 17.089148
COLLEGE_LNG = 82.06599


DB_NAME = "database.db"
UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# ================= DB INIT =================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    


    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         username TEXT UNIQUE NOT NULL,
         email TEXT UNIQUE NOT NULL,
         password TEXT NOT NULL,
         role TEXT NOT NULL DEFAULT 'student',
         bus_id INTEGER,
         photo TEXT DEFAULT 'user.png'
        )

    """)
    # ================= STUDENT COMPLAINTS =================
    conn.execute("""
         CREATE TABLE IF NOT EXISTS complaints (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             user_id INTEGER,
             message TEXT NOT NULL,
             created_at DATETIME DEFAULT CURRENT_TIMESTAMP
         )
    """)


    conn.execute("""
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS buses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bus_number TEXT NOT NULL,
            registration_number TEXT NOT NULL,
            driver_name TEXT NOT NULL,
            route TEXT NOT NULL,
            user_id INTEGER NULL
        )
    """)

    # ✅ GPS LOCATION TABLE
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bus_location (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bus_id INTEGER,
            latitude REAL,
            longitude REAL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # default admin
    conn.execute("""
        INSERT OR IGNORE INTO admin (id, username, password)
        VALUES (1, 'admin', 'admin123')
    """)
        # ================= ADMIN INFO FOR REPORT =================
    conn.execute("""
        CREATE TABLE IF NOT EXISTS admin_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_name TEXT NOT NULL,
            college_name TEXT NOT NULL,
            email TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS admin_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            phone TEXT NOT NULL
        )
    """)

    # default admin info (for report page)
    conn.execute("""
        INSERT OR IGNORE INTO admin_info (id, admin_name, college_name, email)
        VALUES (1, 'Transport Admin', 'Smart College', 'admin@college.edu')
    """)

    # multiple admin contact numbers
    conn.execute("""
        INSERT OR IGNORE INTO admin_contacts (id, admin_id, phone)
        VALUES
        (1, 1, '+91-7981345991'),
        (2, 1, '+91-8919226940'),
        (3, 1, '+91-9000000000')
    """)

    
    conn.commit()
    conn.close()


# ================= DB CONNECTION =================
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


# ================= HELPERS =================
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS



# ================= USER ROUTES =================
from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3

app = Flask(__name__)
app.secret_key = "secret123"


# ---------------- DB CONNECTION ----------------
def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- INDEX ----------------
@app.route("/")
def index():
    return render_template("index.html")


# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        confirm = request.form["confirm_password"]

        # 🔴 PASSWORD MATCH CHECK (ADDED)
        if password != confirm:
            flash("Passwords do not match", "password_error")
            return redirect(url_for("signup"))

        conn = get_db_connection()

        # 🔍 EMAIL CHECK
        if conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone():
            conn.close()
            flash("Email already exists", "email_error")
            return redirect(url_for("signup"))

        # 🔍 USERNAME CHECK
        if conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone():
            conn.close()
            flash("Username already taken", "username_error")
            return redirect(url_for("signup"))

        # ✅ INSERT USER
        conn.execute(
            "INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, 'student')",
            (username, email, password)
        )
        conn.commit()

        # 🔑 AUTO LOGIN
        user = conn.execute(
            "SELECT id, username, role FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        conn.close()

        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]

        return redirect(url_for("dashboard"))

    return render_template("signup.html")


# ---------------- LOGIN ----------------
@app.route("/login", methods=["POST"])
def login():
    user_input = request.form["login_user"]
    password = request.form["login_password"]
    role = request.form.get("role")

    conn = get_db_connection()

    user = conn.execute("""
        SELECT id, username, password, role
        FROM users
        WHERE email = ? OR username = ?
    """, (user_input, user_input)).fetchone()

    if not user:
        conn.close()
        flash("Account does not exist")
        return redirect(url_for("index"))

    if user["password"] != password:
        conn.close()
        flash("Incorrect password")
        return redirect(url_for("index"))

    if role != user["role"]:
        conn.close()
        flash("Incorrect role selected")
        return redirect(url_for("index"))

    conn.close()

    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user["role"]

    return redirect(url_for("dashboard"))





@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("index"))
    return render_template("dashboard.html")


@app.route("/my_bus", methods=["GET", "POST"])
def my_bus():

    if "user_id" not in session:
        return redirect(url_for("index"))

    user_id = session["user_id"]

    conn = get_db_connection()

    # --- get user bus ---
    from datetime import date
    today = date.today().isoformat()

    user = conn.execute("""
        SELECT bus_id, temp_bus_id, temp_bus_date
        FROM users
        WHERE id = ?
    """, (user_id,)).fetchone()

    bus = None
    # 🔁 RESET TEMP BUS IF EXPIRED (AUTO REASSIGN)
    if user and user["temp_bus_id"] and user["temp_bus_date"] != today:
        conn.execute("""
          UPDATE users
         SET temp_bus_id = NULL,
             temp_bus_date = NULL
         WHERE id = ?
        """, (user_id,))
    conn.commit()



    if user:
        # 🔹 TEMP BUS HAS PRIORITY (ONE DAY)
        if user["temp_bus_id"] and user["temp_bus_date"] == today:
            bus = conn.execute(
                "SELECT * FROM buses WHERE id = ?",
                (user["temp_bus_id"],)
            ).fetchone()
            is_temp = True   # 👈 ADD THIS LINE

        elif user["bus_id"]:
            bus = conn.execute(
                "SELECT * FROM buses WHERE id = ?",
                (user["bus_id"],)
            ).fetchone()

    # --- get pickup ---
    pickup = conn.execute(
        "SELECT * FROM pickup_points WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    # --- handle POST ---
    if request.method == "POST":
        bus_number = request.form.get("bus_number")

        bus_row = conn.execute(
            "SELECT id FROM buses WHERE bus_number = ?",
            (bus_number,)
        ).fetchone()

        if bus_row:
            conn.execute(
                "UPDATE users SET bus_id = ? WHERE id = ?",
                (bus_row["id"], user_id)
            )
            conn.commit()
            flash("Bus assigned successfully")
        else:
            flash("Invalid bus number")

        conn.close()
        return redirect(url_for("my_bus"))

    # --- close DB ONCE ---
    conn.close()

    return render_template(
        "my_bus.html",
        bus=bus,
        pickup=pickup,
        is_temp=False
    )





# ================= DRIVER GPS PAGE (✅ ADDED) =================
@app.route("/driver_gps")
def driver_gps():

    if session.get("role") != "driver":
        return redirect(url_for("dashboard"))

    conn = get_db_connection()

    bus = conn.execute("""
        SELECT buses.*
        FROM users
        JOIN buses ON users.bus_id = buses.id
        WHERE users.id = ?
    """, (session["user_id"],)).fetchone()

    conn.close()

    if not bus:
        flash("❌ No bus assigned")
        return redirect(url_for("dashboard"))

    return render_template("driver_gps.html", bus=bus)





# ================= GPS UPDATE (DRIVER) =================
@app.route("/driver/update_location", methods=["POST"])
def driver_update_location():

    if session.get("role") != "driver":
        return jsonify({"error": "unauthorized"}), 403

    data = request.json
    lat = data.get("latitude")
    lng = data.get("longitude")

    if lat is None or lng is None:
        return jsonify({"error": "invalid data"}), 400

    conn = get_db_connection()

    # 🔹 Get driver's bus
    bus = conn.execute(
        "SELECT bus_id FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    if not bus or not bus["bus_id"]:
        conn.close()
        return jsonify({"error": "no bus assigned"}), 400

    bus_id = bus["bus_id"]

    # 🔹 Save / update bus GPS (EXISTING FEATURE — UNCHANGED)
    conn.execute("""
        INSERT INTO bus_location (bus_id, latitude, longitude, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(bus_id) DO UPDATE SET
            latitude = excluded.latitude,
            longitude = excluded.longitude,
            updated_at = CURRENT_TIMESTAMP
    """, (bus_id, lat, lng))

    conn.commit()

    # ======================================================
    # 🔔 NEW: NOTIFICATION TRIGGER (ADDED ONLY)
    # ======================================================

    students = conn.execute("""
        SELECT u.id, p.latitude, p.longitude
        FROM users u
        JOIN pickup_points p ON p.user_id = u.id
        WHERE u.bus_id = ?
    """, (bus_id,)).fetchall()

    for s in students:

        # 🚌 Distance to pickup
        d_pickup = haversine(
            lat, lng,
            s["latitude"], s["longitude"]
        )

        if d_pickup <= 500:
            send_notification(
                s["id"],
                "near_pickup",
                "🚌 Bus is near your pickup point"
            )

        # 🏫 Distance to college
        d_college = haversine(
            lat, lng,
            COLLEGE_LAT, COLLEGE_LNG
        )

        if d_college <= 150:
            send_notification(
                s["id"],
                "college_reached",
                "🏫 Bus has reached the college"
            )

    # ======================================================

    conn.close()
    return jsonify({"status": "ok"})








# ================= GPS FETCH (STUDENT) =================
@app.route("/bus_location/<int:bus_id>")
def bus_location(bus_id):
    conn = get_db_connection()
    location = conn.execute("""
        SELECT latitude, longitude
        FROM bus_location
        WHERE bus_id=?
        ORDER BY updated_at DESC
        LIMIT 1
    """, (bus_id,)).fetchone()
    conn.close()

    if location:
        return jsonify(dict(location))

    return jsonify({"error": "No GPS data"})


# ================= PROFILE =================
@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        return redirect(url_for("index"))

    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()

    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        current_password = request.form["current_password"]
        new_password = request.form["new_password"]

        if current_password != user["password"]:
            flash("❌ Current password incorrect")
            return redirect(url_for("profile"))

        photo = user["photo"]
        if "photo" in request.files:
            file = request.files["photo"]
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                photo = filename

        conn.execute("""
            UPDATE users
            SET username=?, email=?, password=?, photo=?
            WHERE id=?
        """, (
            username,
            email,
            new_password if new_password else user["password"],
            photo,
            session["user_id"]
        ))

        conn.commit()
        conn.close()

        session["username"] = username
        flash("✅ Profile updated")
        return redirect(url_for("profile"))

    conn.close()
    return render_template("profile.html", user=user)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ================= ADMIN =================



@app.route("/admin/dashboard")
def admin_dashboard():
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("admin_login"))

    conn = get_db_connection()

    # 🔹 EXISTING STATS
    total_students = conn.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'student'"
    ).fetchone()[0]

    total_drivers = conn.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'driver'"
    ).fetchone()[0]

    total_buses = conn.execute(
        "SELECT COUNT(*) FROM buses"
    ).fetchone()[0]

    active_tracking = conn.execute(
        "SELECT COUNT(DISTINCT user_id) FROM active_students"
    ).fetchone()[0]

    # 🔴 NEW: FETCH SOS ALERTS (LATEST FIRST)
    sos_alerts = conn.execute("""
        SELECT *
        FROM sos_reports
        ORDER BY created_at DESC
    """).fetchall()

    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_students=total_students,
        total_drivers=total_drivers,
        total_buses=total_buses,
        active_tracking=active_tracking,
        sos_alerts=sos_alerts   # 🔴 ADD THIS
    )


# ================= ADMIN DELETE SOS =================
@app.route("/admin/delete_sos/<int:sos_id>", methods=["POST"])
def admin_delete_sos(sos_id):

    if session.get("role") != "admin":
        return redirect(url_for("admin_login"))


    conn = get_db_connection()
    conn.execute(
     "DELETE FROM sos_reports WHERE id = ?",
    (sos_id,)
)

    conn.commit()
    conn.close()

    flash("SOS resolved")
    return redirect(url_for("admin_dashboard"))


#================= ADMIN ADD/VIEW/DELETE BUS =================
@app.route("/admin/add_bus", methods=["GET", "POST"])
def add_bus():
    if "user_id" not in session or session.get("role") != "admin":
        flash("❌ Admin access only")
        return redirect(url_for("admin_login"))

    # rest of your code...

    conn = get_db_connection()
    users = conn.execute("SELECT id, username FROM users").fetchall()

    if request.method == "POST":
        conn.execute("""
            INSERT INTO buses (bus_number, registration_number, driver_name, route, user_id)
            VALUES (?, ?, ?, ?, ?)
        """, (
            request.form["bus_number"],
            request.form["registration_number"],
            request.form["driver_name"],
            request.form["route"],
            request.form.get("user_id") or None
        ))
        conn.commit()
        conn.close()

        flash("✅ Bus added")
        return redirect(url_for("view_buses"))

    conn.close()
    return render_template("add_bus.html", users=users)


@app.route("/admin/buses")
def view_buses():
    if "user_id" not in session or session.get("role") != "admin":
        flash("❌ Admin access only")
        return redirect(url_for("admin_login"))

    # rest of your code...


    conn = get_db_connection()
    buses = conn.execute("SELECT * FROM buses").fetchall()
    conn.close()

    return render_template("view_buses.html", buses=buses)


@app.route("/admin/delete_bus/<int:bus_id>")
def delete_bus(bus_id):
    if "user_id" not in session or session.get("role") != "admin":

        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    conn.execute("DELETE FROM buses WHERE id=?", (bus_id,))
    conn.commit()
    conn.close()

    flash("🗑 Bus deleted")
    return redirect(url_for("view_buses"))


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin_login"))
@app.route("/admin/add_driver", methods=["GET", "POST"])
def admin_add_driver():

    if "user_id" not in session or session.get("role") != "admin":
        flash("❌ Admin access only")
        return redirect(url_for("admin_dashboard"))

    conn = get_db_connection()
    buses = conn.execute("SELECT * FROM buses").fetchall()

    if request.method == "POST":
        # 🔹 READ FORM DATA
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        bus_id = request.form["bus_id"]
        phone = request.form["phone"]

        # 🔹 CHECK DUPLICATE USERNAME
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        if existing:
            conn.close()
            flash("❌ Username already exists")
            return redirect(url_for("admin_add_driver"))

        # 🔹 CREATE DRIVER USER (WITH PHONE)
        conn.execute("""
            INSERT INTO users (username, email, password, role, bus_id, phone)
            VALUES (?, ?, ?, 'driver', ?, ?)
        """, (username, email, password, bus_id, phone))

        # 🔹 GET DRIVER USER ID
        driver_user_id = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,)
        ).fetchone()["id"]

        # 🔹 MAP DRIVER TO BUS
        conn.execute("""
            INSERT INTO drivers (user_id, bus_id)
            VALUES (?, ?)
        """, (driver_user_id, bus_id))

        conn.commit()
        conn.close()

        flash("✅ Driver created successfully")
        return redirect(url_for("admin_dashboard"))

    conn.close()
    return render_template("admin_add_driver.html", buses=buses)



    

# ================= REPORT PAGE =================
@app.route("/report")
def report():
    if "user_id" not in session:
        return redirect(url_for("index"))

    conn = get_db_connection()

    admin = conn.execute("SELECT * FROM admin_info WHERE id=1" ).fetchone()

    contacts = conn.execute("SELECT phone FROM admin_contacts WHERE admin_id=1").fetchall()

    conn.close()

    return render_template("report.html", admin=admin, contacts=contacts)
#========================complaint======================
@app.route("/submit_complaint", methods=["POST"])
def submit_complaint():
    if "user_id" not in session:
        return redirect(url_for("index"))

    subject = request.form.get("subject")
    message = request.form.get("message")

    if not subject or not message:
        flash("❌ All fields are required")
        return redirect(url_for("report"))

    conn = get_db_connection()
    conn.execute("""
        INSERT INTO complaints (user_id, subject, message)
        VALUES (?, ?, ?)
    """, (session["user_id"], subject, message))
    conn.commit()
    conn.close()

    flash("✅ Complaint submitted successfully")
    return redirect(url_for("report"))

#============================admincomplaints reader======================= 
@app.route("/admin/complaints")
def admin_complaints():
    if "user_id" not in session or session.get("role") != "admin":
        flash("❌ Admin access only")
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    complaints = conn.execute("""
        SELECT 
            complaints.id,
            complaints.subject,
            complaints.message,
            complaints.created_at,
            users.username,
            users.email
        FROM complaints
        JOIN users ON complaints.user_id = users.id
        ORDER BY complaints.created_at DESC
    """).fetchall()
    conn.close()

    return render_template("admin_complaints.html", complaints=complaints)


#===================FLASK ROUTE (BACKEND)=======================================
@app.route("/student/set_pickup", methods=["GET", "POST"])
def set_pickup():

    # 🔒 Only students
    if "user_id" not in session or session.get("role") != "student":
        return redirect(url_for("index"))

    user_id = session["user_id"]
    conn = get_db_connection()

    # 🔍 Get student's assigned bus
    student = conn.execute(
        "SELECT bus_id FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if not student or not student["bus_id"]:
        conn.close()
        flash("❌ Please assign a bus before setting pickup point")
        return redirect(url_for("my_bus"))

    bus_id = student["bus_id"]

    # 🔍 Existing pickup (if any)
    existing = conn.execute(
        "SELECT * FROM pickup_points WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    if request.method == "POST":
        pickup_name = request.form["pickup_name"]
        lat = request.form["latitude"]
        lng = request.form["longitude"]

        if existing:
            conn.execute("""
                UPDATE pickup_points
                SET pickup_name = ?, latitude = ?, longitude = ?, bus_id = ?
                WHERE user_id = ?
            """, (pickup_name, lat, lng, bus_id, user_id))
        else:
            conn.execute("""
                INSERT INTO pickup_points
                (user_id, bus_id, pickup_name, latitude, longitude)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, bus_id, pickup_name, lat, lng))

        conn.commit()
        conn.close()

        flash("✅ Pickup point saved successfully")
        return redirect(url_for("my_bus"))

    conn.close()
    return render_template("set_pickup.html")




#-============================ASSIGN BUS BY USER IT SELF=======================
@app.route("/assign_bus/<int:bus_id>")
def assign_bus(bus_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "student":
        return redirect(url_for("dashboard"))

    conn = sqlite3.connect("database.db")
    conn.execute(
        "UPDATE users SET bus_id = ? WHERE id = ?",
        (bus_id, session["user_id"])
    )
    conn.commit()
    conn.close()

    return redirect(url_for("my_bus"))







@app.route("/student/get_location")
def student_get_location():

    if "user_id" not in session:
        return jsonify({})

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row

    user = conn.execute("""
        SELECT bus_id, temp_bus_id, temp_bus_date
        FROM users
        WHERE id = ?
    """, (session["user_id"],)).fetchone()

    if not user:
        conn.close()
        return jsonify({})

    from datetime import date, datetime, timezone, timedelta
    today = date.today().isoformat()

    # ✅ TEMP-AWARE BUS SELECTION
    bus_id = (
        user["temp_bus_id"]
        if user["temp_bus_id"] and user["temp_bus_date"] == today
        else user["bus_id"]
    )

    if not bus_id:
        conn.close()
        return jsonify({})

    row = conn.execute("""
        SELECT latitude, longitude, speed, updated_at
        FROM bus_location
        WHERE bus_id = ?
        ORDER BY updated_at DESC
        LIMIT 1
    """, (bus_id,)).fetchone()

    eta_row = conn.execute("""
        SELECT eta FROM bus_status WHERE bus_id = ?
    """, (bus_id,)).fetchone()

    conn.close()

    if not row:
        return jsonify({"online": False})

    last_update = datetime.fromisoformat(row["updated_at"]).replace(
        tzinfo=timezone.utc
    )

    now = datetime.now(timezone.utc)
    age = int((now - last_update).total_seconds())

    online = age <= 20

    return jsonify({
        "latitude": float(row["latitude"]) if row["latitude"] else None,
        "longitude": float(row["longitude"]) if row["longitude"] else None,
        "speed": float(row["speed"]) if row["speed"] is not None else None,
        "eta": eta_row["eta"] if eta_row else None,
        "online": online,
        "age": age,
        "last_update": row["updated_at"]
    })









@app.route("/route_data/<int:bus_id>")
def route_data(bus_id):
    conn = get_db_connection()

    # get active students of THIS bus
    pickups = conn.execute("""
        SELECT p.latitude, p.longitude, u.username
        FROM pickup_points p
        JOIN users u ON u.id = p.user_id
        JOIN active_students a ON a.user_id = p.user_id
        WHERE a.bus_id = ?
    """, (bus_id,)).fetchall()


    conn.close()

    return {
        "pickups": [
                 {
                "lat": r["latitude"],
                "lng": r["longitude"],
                "name": r["username"]
             }
             for r in pickups
         ],
         "destination": {
              "lat": 17.089148,
              "lng": 82.06599
         }
    }








@app.route("/student/get_pickup")
def student_get_pickup():

    if "user_id" not in session:
        return jsonify({})

    conn = get_db_connection()

    pickup = conn.execute("""
        SELECT latitude, longitude
        FROM pickup_points
        WHERE user_id = ?
    """, (session["user_id"],)).fetchone()

    conn.close()

    if pickup:
        return jsonify({
            "latitude": pickup["latitude"],
            "longitude": pickup["longitude"]
        })

    return jsonify({})

@app.route("/driver/get_pickups")
def driver_get_pickups():

    if session.get("role") != "driver":
        return jsonify([])

    conn = get_db_connection()

    # 1️⃣ Get driver's bus
    row = conn.execute(
        "SELECT bus_id FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    if not row or not row["bus_id"]:
        conn.close()
        return jsonify([])

    bus_id = row["bus_id"]

    # 2️⃣ Fetch pickups
    # RULE:
    # - If a TEMP pickup exists for a student → hide original pickup
    pickups = conn.execute("""
        SELECT
            user_id,
            latitude,
            longitude,
            pickup_name,
            is_temp
        FROM pickup_points
        WHERE bus_id = ?
          AND (
              is_temp = 1
              OR user_id NOT IN (
                  SELECT user_id
                  FROM pickup_points
                  WHERE is_temp = 1
              )
          )
    """, (bus_id,)).fetchall()

    conn.close()

    # 3️⃣ Send to frontend
    return jsonify([
        {
            "lat": p["latitude"],
            "lng": p["longitude"],
            "name": p["pickup_name"],
            "is_temp": p["is_temp"] == 1
        }
        for p in pickups
    ])



@app.route("/driver/update_eta", methods=["POST"])
def driver_update_eta():

    if session.get("role") != "driver":
        return jsonify({"error": "unauthorized"}), 403

    data = request.json
    eta = data.get("eta")

    conn = get_db_connection()

    bus = conn.execute(
        "SELECT bus_id FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    if not bus or not bus["bus_id"]:
        conn.close()
        return jsonify({"error": "no bus"}), 400

    conn.execute("""
        INSERT INTO bus_status (bus_id, eta)
        VALUES (?, ?)
        ON CONFLICT(bus_id) DO UPDATE SET
            eta = excluded.eta,
            updated_at = CURRENT_TIMESTAMP
    """, (bus["bus_id"], eta))

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})

@app.route("/student/get_eta")
def student_get_eta():

    if "user_id" not in session:
        return jsonify({})

    conn = get_db_connection()

    bus = conn.execute(
        "SELECT bus_id FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    if not bus or not bus["bus_id"]:
        conn.close()
        return jsonify({})

    status = conn.execute(
        "SELECT eta FROM bus_status WHERE bus_id = ?",
        (bus["bus_id"],)
    ).fetchone()

    conn.close()

    if status:
        return jsonify({"eta": status["eta"]})

    return jsonify({})

@app.route("/student/get_bus_pickups")
def student_get_bus_pickups():
    if "user_id" not in session:
        return jsonify([])

    conn = get_db_connection()
    user = conn.execute(
        "SELECT bus_id FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()

    pickups = []
    if user and user["bus_id"]:
        pickups = conn.execute(
            "SELECT latitude, longitude FROM pickup_points WHERE bus_id=?",
            (user["bus_id"],)
        ).fetchall()

    conn.close()
    return jsonify([
        {"lat": p["latitude"], "lng": p["longitude"]}
        for p in pickups
    ])


@app.route("/admin/delete_user/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    if session.get("role") != "admin":
        return redirect(url_for("dashboard"))

    conn = get_db_connection()

    # Unassign driver from bus if exists
    conn.execute(
        "UPDATE buses SET user_id = NULL WHERE user_id = ?",
        (user_id,)
    )

    # Delete user
    conn.execute(
        "DELETE FROM users WHERE id = ?",
        (user_id,)
    )

    conn.commit()
    conn.close()

    flash("User deleted successfully")
    return redirect(url_for("admin_data"))
@app.route("/admin/delete_bus/<int:bus_id>", methods=["POST"])
def admin_delete_bus(bus_id):

    if session.get("role") != "admin":
        return redirect(url_for("dashboard"))

    conn = get_db_connection()
    conn.execute("DELETE FROM buses WHERE id = ?", (bus_id,))
    conn.commit()
    conn.close()

    flash("Bus deleted successfully")
    return redirect(url_for("admin_data"))

@app.route("/admin/disable_user/<int:user_id>", methods=["POST"])
def disable_user(user_id):
    if session.get("role") != "admin":
        return redirect(url_for("dashboard"))

    conn = get_db_connection()
    conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    flash("User disabled")
    return redirect(url_for("admin_data"))
@app.route("/admin/disable_bus/<int:bus_id>", methods=["POST"])
def disable_bus(bus_id):
    if session.get("role") != "admin":
        return redirect(url_for("dashboard"))

    conn = get_db_connection()
    conn.execute("UPDATE buses SET is_active = 0 WHERE id = ?", (bus_id,))
    conn.commit()
    conn.close()

    flash("Bus disabled")
    return redirect(url_for("admin_data"))
@app.route("/admin/data")
def admin_data():
    if session.get("role") != "admin":
        return redirect(url_for("dashboard"))

    search = request.args.get("search", "")
    role = request.args.get("role", "")

    conn = get_db_connection()

    users = conn.execute("""
        SELECT id, username, email, role
        FROM users
        WHERE is_active = 1
          AND (username LIKE ? OR email LIKE ?)
          AND (? = '' OR role = ?)
    """, (
        f"%{search}%",
        f"%{search}%",
        role,
        role
    )).fetchall()

    buses = conn.execute("""
        SELECT id, bus_number, route, driver_name
        FROM buses
    """).fetchall()

    conn.close()

    return render_template(
        "admin_data.html",
        users=users,
        buses=buses
    )


    return render_template("admin_data.html", users=users)



import math

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(dlambda / 2) ** 2

    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))
@app.route("/driver/pickups")
def driver_pickups():

    if session.get("role") != "driver":
        return jsonify([])

    conn = get_db_connection()

    # 1️⃣ get driver's bus
    driver = conn.execute(
        "SELECT bus_id FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()

    if not driver or not driver["bus_id"]:
        conn.close()
        return jsonify([])

    bus_id = driver["bus_id"]

    # 2️⃣ get bus location
    bus_loc = conn.execute("""
        SELECT latitude, longitude
        FROM bus_location
        WHERE bus_id=?
        ORDER BY updated_at DESC
        LIMIT 1
    """, (bus_id,)).fetchone()

    if not bus_loc:
        conn.close()
        return jsonify([])

    driver_lat = bus_loc["latitude"]
    driver_lng = bus_loc["longitude"]

    # 3️⃣ get pickup points
    pickups = conn.execute("""
        SELECT p.latitude, p.longitude, u.username
        FROM pickup_points p
        JOIN users u ON u.id = p.user_id
        WHERE p.bus_id = ?
    """, (bus_id,)).fetchall()

    result = []

    # 4️⃣ calculate distance + status
    for p in pickups:
        dist = haversine(
            driver_lat,
            driver_lng,
            p["latitude"],
            p["longitude"]
        )

        if dist < 150:
            status = "Reached"
        elif dist < 500:
            status = "Approaching"
        else:
            status = "Pending"

        result.append({
            "name": p["username"],
            "distance": round(dist),
            "status": status
        })

    conn.close()

    # 5️⃣ sort nearest first
    result.sort(key=lambda x: x["distance"])

    return jsonify(result)
@app.route("/student/bus_status")
def student_bus_status():

    if "user_id" not in session:
        return jsonify({})

    conn = get_db_connection()

    # get student's pickup + bus
    pickup = conn.execute("""
        SELECT latitude, longitude, bus_id
        FROM pickup_points
        WHERE user_id = ?
    """, (session["user_id"],)).fetchone()

    if not pickup:
        conn.close()
        return jsonify({})

    # get latest bus location
    bus_loc = conn.execute("""
        SELECT latitude, longitude
        FROM bus_location
        WHERE bus_id = ?
        ORDER BY updated_at DESC
        LIMIT 1
    """, (pickup["bus_id"],)).fetchone()

    if not bus_loc:
        conn.close()
        return jsonify({})

    # distance to pickup
    dist_pickup = haversine(
        bus_loc["latitude"],
        bus_loc["longitude"],
        pickup["latitude"],
        pickup["longitude"]
    )

    # distance to college
    dist_college = haversine(
        bus_loc["latitude"],
        bus_loc["longitude"],
        COLLEGE_LAT,
        COLLEGE_LNG
    )

    # status logic
    if dist_college < 150:
        status = "Arrived to College"
    elif dist_pickup < 150:
        status = "Arrived"
    elif dist_pickup < 500:
        status = "Approaching"
    else:
        status = "On the way"

    conn.close()

    return jsonify({
        "distance_m": round(dist_pickup),
        "distance_km": round(dist_pickup / 1000, 2),
        "status": status
    })





def get_status(distance):
    if distance < 150:
        return "Arrived"
    elif distance < 500:
        return "Approaching"
    else:
        return "Pending"

@app.route("/driver/sos", methods=["POST"])
def driver_sos():

    if session.get("role") != "driver":
        return jsonify({"error": "unauthorized"}), 403

    data = request.get_json(silent=True) or {}
    lat = data.get("latitude")
    lng = data.get("longitude")

    if not lat or not lng:
        return jsonify({"error": "location missing"}), 400

    conn = get_db_connection()

    row = conn.execute("""
        SELECT u.username, u.phone, b.bus_number
        FROM users u
        JOIN buses b ON u.bus_id = b.id
        WHERE u.id = ?
    """, (session["user_id"],)).fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "no bus assigned"}), 400

    conn.execute("""
        INSERT INTO sos_reports
        (bus_number, driver_name, contact, latitude, longitude, message)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        row["bus_number"],
        row["username"],
        row["phone"],
        lat,
        lng,
        "🚨 SOS triggered by driver"
    ))
    send_sos_email(
    row["bus_number"],
    row["username"],
    row["phone"],
    lat,
    lng
)


    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})

# ================= SEND SOS EMAIL (EXAMPLE) =================
def send_sos_email(bus, driver, phone, lat, lng):

    msg = EmailMessage()
    msg["Subject"] = "🚨 BUS SOS ALERT"
    msg["From"] = "YOUR_GMAIL@gmail.com"
    msg["To"] = "manikantasai218@gmail.com"

    msg.set_content(f"""
🚨 EMERGENCY SOS RECEIVED

Bus Number : {bus}
Driver     : {driver}
Phone      : {phone}

Location:
https://www.google.com/maps?q={lat},{lng}
""")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(
    "manikantasai218@gmail.com",
    "hllivnphszsdqzmy"
)

        server.send_message(msg)

import math

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@app.route("/driver/pickup_order")
def driver_pickup_order():

    if session.get("role") != "driver":
        return jsonify([])

    conn = get_db_connection()

    # driver bus
    bus_id = conn.execute(
        "SELECT bus_id FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()["bus_id"]

    # bus live location
    bus = conn.execute("""
        SELECT latitude, longitude
        FROM bus_location
        WHERE bus_id=?
    """, (bus_id,)).fetchone()

    if not bus:
        conn.close()
        return jsonify([])

    students = conn.execute("""
    SELECT
        u.username,
        p.pickup_name,
        p.latitude,
        p.longitude
    FROM pickup_points p
    JOIN users u ON u.id = p.user_id
    WHERE p.bus_id = ?
 """, (bus_id,)).fetchall()


    result = []

    for s in students:
        d = haversine(
            bus["latitude"], bus["longitude"],
            s["latitude"], s["longitude"]
        )


        if d <= 150:
            status = "Reached"
        elif d <= 500:
            status = "Approaching"
        else:
            status = "Pending"

        result.append({
            "name": s["pickup_name"],

            "distance": int(d),
            "status": status
        })

    result.sort(key=lambda x: x["distance"])

    conn.close()
    return jsonify(result)

@app.route("/driver/ordered_pickups")
def driver_ordered_pickups():

    # 🔐 Only driver
    if session.get("role") != "driver":
        return jsonify([])

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row

    # 1️⃣ Get bus_id
    row = conn.execute(
        "SELECT bus_id FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()

    if not row or not row["bus_id"]:
        conn.close()
        return jsonify([])

    bus_id = row["bus_id"]

    # 2️⃣ Get live bus location
    bus = conn.execute(
        "SELECT latitude, longitude FROM bus_location WHERE bus_id=?",
        (bus_id,)
    ).fetchone()

    if not bus:
        conn.close()
        return jsonify([])

    bus_lat = float(bus["latitude"])
    bus_lng = float(bus["longitude"])

    # 3️⃣ Get pickup points
    pickups = conn.execute("""
        SELECT
            pickup_name,
            latitude,
            longitude,
            pickup_reached,
            is_temp
        FROM pickup_points
        WHERE bus_id=?
    """, (bus_id,)).fetchall()

    from math import radians, sin, cos, sqrt, atan2

    def distance_m(lat1, lng1, lat2, lng2):
        R = 6371000
        dlat = radians(lat2 - lat1)
        dlng = radians(lng2 - lng1)
        a = (
            sin(dlat / 2) ** 2 +
            cos(radians(lat1)) *
            cos(radians(lat2)) *
            sin(dlng / 2) ** 2
        )
        return int(2 * R * atan2(sqrt(a), sqrt(1 - a)))

    result = []

    for p in pickups:
        d = distance_m(
            bus_lat, bus_lng,
            float(p["latitude"]),
            float(p["longitude"])
        )

        # 🔒 MONOTONIC STATUS (NO WRITES)
        if p["pickup_reached"] == 1:
            status = "Reached"
        elif d <= 500:
            status = "Approaching"
        else:
            status = "Pending"

        result.append({
            "name": p["pickup_name"],
            "lat": p["latitude"],
            "lng": p["longitude"],
            "distance": d,
            "status": status,
            "is_temp": bool(p["is_temp"])
        })

    conn.close()

    # nearest first
    result.sort(key=lambda x: x["distance"])

    return jsonify(result)


# ================= STUDENT NOTIFICATIONS =================
@app.route("/student/notifications")
def student_notifications_api():

    if session.get("role") != "student":
        return jsonify(None)

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row

    row = conn.execute("""
        SELECT message
        FROM student_notifications
        WHERE user_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
    """, (session["user_id"],)).fetchone()

    conn.close()

    return jsonify(row["message"] if row else None)



@app.route("/student/pickup_order")
def student_pickup_order():

    if session.get("role") != "student":
        return jsonify({})

    conn = get_db_connection()

    student = conn.execute("""
        SELECT id, bus_id FROM users WHERE id=?
    """, (session["user_id"],)).fetchone()

    if not student or not student["bus_id"]:
        conn.close()
        return jsonify({})

    bus_id = student["bus_id"]

    bus = conn.execute("""
        SELECT latitude, longitude
        FROM bus_location
        WHERE bus_id=?
    """, (bus_id,)).fetchone()

    driver_started = bus is not None

    students = conn.execute("""
        SELECT
            p.user_id,
            p.pickup_name,
            p.latitude,
            p.longitude
        FROM pickup_points p
        WHERE p.bus_id=?
    """, (bus_id,)).fetchall()

    pickups = []

    for s in students:

        if not bus:
            d = 999999
            status = "Pending"
        else:
            d = haversine(
                bus["latitude"], bus["longitude"],
                s["latitude"], s["longitude"]
            )

            if d <= 150:
                status = "Reached"
            elif d <= 500:
                status = "Approaching"
            else:
                status = "Pending"

        pickups.append({
            "name": s["pickup_name"],
            "distance": int(d),
            "status": status,
            "is_me": s["user_id"] == student["id"]
        })

    pickups.sort(key=lambda x: x["distance"])

    college_reached = False
    if bus:
        college_dist = haversine(
            bus["latitude"], bus["longitude"],
            COLLEGE_LAT, COLLEGE_LNG
        )
        college_reached = college_dist <= 200

    conn.close()

    return jsonify({
        "driver_started": driver_started,
        "college_reached": college_reached,
        "pickups": pickups
    })


def is_driver_started(bus_id, conn):
    row = conn.execute("""
        SELECT 1 FROM bus_location WHERE bus_id=?
    """, (bus_id,)).fetchone()
    return row is not None
from datetime import date
# ================= CHECK BUS MISSED PICKUP =================
def check_bus_missed(bus_lat, bus_lng, pickup_lat, pickup_lng):
    """
    Returns True if bus has already passed pickup
    """
    from math import radians, cos, sin, sqrt, atan2

    R = 6371000

    dlat = radians(pickup_lat - bus_lat)
    dlng = radians(pickup_lng - bus_lng)

    a = sin(dlat/2)**2 + cos(radians(bus_lat)) * cos(radians(pickup_lat)) * sin(dlng/2)**2
    dist = 2 * R * atan2(sqrt(a), sqrt(1-a))

    # 🚨 If bus is MORE than 800m away → missed
    return dist > 800
# ================= STUDENT DRIVER CONTACT =================
@app.route("/student/driver_contact")
def student_driver_contact():

    if session.get("role") != "student":
        return jsonify({})

    conn = get_db_connection()

    row = conn.execute("""
        SELECT u.phone, b.bus_number
        FROM users u
        JOIN buses b ON u.bus_id = b.id
        WHERE u.role = 'driver'
          AND b.id = (
              SELECT bus_id FROM users WHERE id = ?
          )
    """, (session["user_id"],)).fetchone()

    conn.close()

    if not row:
        return jsonify({})

    return jsonify({
        "phone": row["phone"],
        "bus": row["bus_number"]
    })


from datetime import date
# ================= STUDENT MISS BUS =================
# ================= STUDENT MISSED BUS (SAFE) =================
@app.route("/student/miss_bus", methods=["POST"])
def student_miss_bus():

    if session.get("role") != "student":
        return jsonify({"error": "unauthorized"}), 403

    # ✅ UI STATE FLAG
    session["missed_bus"] = True

    return jsonify({
        "status": "ok",
        "message": "Missed bus confirmed. Choose a nearby bus for today."
    })



from datetime import date

# ================= STUDENT MISSED BUS =================
@app.route("/student/missed_bus", methods=["POST"])
def missed_bus():

    if session.get("role") != "student":
        return redirect(url_for("dashboard"))

    # TEMP PLACEHOLDER (logic comes next)
    flash("⚠️ Missed bus request received")
    return redirect(url_for("dashboard"))

# ================= STUDENT ASSIGN TEMP BUS =================
@app.route("/student/assign_temp_bus/<int:bus_id>")
def assign_temp_bus(bus_id):

    if session.get("role") != "student":
        return redirect(url_for("dashboard"))

    from datetime import date
    today = date.today().isoformat()

    conn = get_db_connection()

    student_id = session["user_id"]

    # 1️⃣ Get student's ORIGINAL pickup
    pickup = conn.execute("""
        SELECT pickup_name, latitude, longitude
        FROM pickup_points
        WHERE user_id = ?
    """, (student_id,)).fetchone()

    if not pickup:
        conn.close()
        flash("❌ No pickup point found")
        return redirect(url_for("dashboard"))

    # 2️⃣ Assign TEMP bus to student
    conn.execute("""
        UPDATE users
        SET temp_bus_id = ?, temp_bus_date = ?
        WHERE id = ?
    """, (bus_id, today, student_id))

    # 3️⃣ INSERT TEMP pickup for that bus (FOR TODAY ONLY)
    conn.execute("""
        INSERT INTO pickup_points
        (user_id, pickup_name, latitude, longitude, bus_id, is_temp, temp_date)
        VALUES (?, ?, ?, ?, ?, 1, ?)
    """, (
        student_id,
        pickup["pickup_name"] + " (TEMP)",
        pickup["latitude"],
        pickup["longitude"],
        bus_id,
        today
    ))

    conn.commit()
    conn.close()

    flash("✅ Temporary bus + pickup assigned for TODAY")
    return redirect(url_for("dashboard"))









# ================= STUDENT ASSIGN TEMP BUS (ONE DAY) =================
@app.route("/student/assign_temp_bus/<int:bus_id>")
def student_assign_temp_bus(bus_id):

    if session.get("role") != "student":
        return redirect(url_for("dashboard"))

    from datetime import date
    today = date.today().isoformat()

    conn = get_db_connection()

    # save temp bus for today only
    conn.execute("""
        UPDATE users
        SET temp_bus_id = ?, temp_bus_date = ?
        WHERE id = ?
    """, (bus_id, today, session["user_id"]))

    conn.commit()
    conn.close()

    flash("✅ Temporary bus assigned for today only")
    return redirect(url_for("dashboard"))
from datetime import date
# ================= RESTORE TEMP BUS ASSIGNMENTS =================
def restore_temp_bus_assignments():

    today = date.today().isoformat()

    conn = get_db_connection()
    conn.execute("""
        UPDATE users
        SET temp_bus_id = NULL,
            temp_bus_date = NULL
        WHERE temp_bus_date IS NOT NULL
          AND temp_bus_date <> ?
    """, (today,))
    conn.commit()
    conn.close()



@app.route("/student/missed/nearby-buses")
def student_missed_nearby_buses():

    if session.get("role") != "student":
        return jsonify([])

    user_id = session["user_id"]
    conn = get_db_connection()

    pickup = conn.execute("""
        SELECT latitude, longitude
        FROM pickup_points
        WHERE user_id = ?
    """, (user_id,)).fetchone()

    if not pickup:
        conn.close()
        return jsonify([])

    pickup_lat = pickup["latitude"]
    pickup_lng = pickup["longitude"]

    

    buses = conn.execute("""
    SELECT
        b.id AS bus_id,
        b.bus_number,
        bl.latitude,
        bl.longitude
    FROM bus_location bl
    JOIN buses b ON b.id = bl.bus_id
    WHERE b.is_active = 1
 """).fetchall()


    results = []

    for bus in buses:

        dist = haversine(
            pickup_lat,
            pickup_lng,
            bus["latitude"],
            bus["longitude"]
        )

        if dist > 30000:
            continue

       # if dist <= 150:
        #    continue

        results.append({
            "bus_id": bus["bus_id"],
            "bus_number": bus["bus_number"],
            "distance": int(dist)
        })

    conn.close()

    results.sort(key=lambda x: x["distance"])
    return jsonify(results)

@app.route("/student/missed/assign-bus/<int:bus_id>")
def student_missed_assign_bus(bus_id):

    if session.get("role") != "student":
        return redirect(url_for("dashboard"))

    today = date.today().isoformat()
    user_id = session["user_id"]

    conn = get_db_connection()

    conn.execute("""
        UPDATE users
        SET temp_bus_id = ?, temp_bus_date = ?
        WHERE id = ?
    """, (bus_id, today, user_id))
    # 🔄 Move pickup to temporary bus
    conn.execute("""
     UPDATE pickup_points
     SET bus_id = ?, is_temp = 1, temp_date = ?
     WHERE user_id = ?
    """, (bus_id, today, user_id))


    conn.commit()
    conn.close()

    flash("✅ Temporary bus assigned for today")
    return redirect(url_for("my_bus"))
from datetime import date

def restore_expired_temp_bus_and_pickups():

    today = date.today().isoformat()
    conn = get_db_connection()

    # 1️⃣ find students whose temp bus expired
    rows = conn.execute("""
        SELECT id, bus_id
        FROM users
        WHERE temp_bus_id IS NOT NULL
          AND temp_bus_date <> ?
    """, (today,)).fetchall()

    for row in rows:
        user_id = row["id"]
        original_bus_id = row["bus_id"]

        # 2️⃣ restore pickup back to original bus
        conn.execute("""
            UPDATE pickup_points
            SET bus_id = ?, is_temp = 0, temp_date = NULL
            WHERE user_id = ?
        """, (original_bus_id, user_id))

    # 3️⃣ clear temp bus flags
    conn.execute("""
        UPDATE users
        SET temp_bus_id = NULL,
            temp_bus_date = NULL
        WHERE temp_bus_date IS NOT NULL
          AND temp_bus_date <> ?
    """, (today,))

    conn.commit()
    conn.close()

@app.route("/student/set_pickup", methods=["POST"])
def set_pickup_api():

    if session.get("role") != "student":
        return jsonify({"status": "error"})

    data = request.json
    lat = data["latitude"]
    lng = data["longitude"]

    conn = get_db_connection()
    conn.execute("""
        UPDATE pickup_points
        SET latitude = ?, longitude = ?
        WHERE user_id = ?
    """, (lat, lng, session["user_id"]))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})

# ================= BUS MESSAGES =================
@app.route("/messages/send", methods=["POST"])
def send_message():
    if "user_id" not in session:
        return jsonify({"error": "Login required"}), 403

    message = request.json.get("message", "").strip()
    if not message:
        return jsonify({"error": "Empty message"}), 400

    conn = get_db_connection()

    user = conn.execute(
        "SELECT role, bus_id FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    if not user or not user["bus_id"]:
        return jsonify({"error": "No bus assigned"}), 400

    conn.execute(
        """
        INSERT INTO bus_messages (bus_id, sender_id, sender_role, message)
        VALUES (?, ?, ?, ?)
        """,
        (user["bus_id"], session["user_id"], user["role"], message)
    )

    conn.commit()
    return jsonify({"success": True})

# ================= GET BUS MESSAGES =================
@app.route("/messages")
def get_messages():
    if "user_id" not in session:
        return jsonify([])

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row

    # get logged-in user's bus
    user = conn.execute(
        "SELECT role, bus_id FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    if not user or not user["bus_id"]:
        return jsonify([])

    # delete messages older than 6 hours
    conn.execute("""
        DELETE FROM bus_messages
        WHERE created_at < DATETIME('now', '-6 hours')
    """)
    conn.commit()

    # fetch messages with username
    messages = conn.execute("""
        SELECT
            bm.message,
            bm.sender_role,
            u.username,
            bm.created_at
        FROM bus_messages bm
        JOIN users u ON u.id = bm.sender_id
        WHERE bm.bus_id = ?
        ORDER BY bm.created_at ASC
    """, (user["bus_id"],)).fetchall()

    return jsonify([dict(m) for m in messages])

# ================= ADMIN SEND MESSAGE TO ALL STUDENTS =================
@app.route("/admin/send_message", methods=["POST"])
def admin_send_message():
    if session.get("role") != "admin":
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    message = data.get("message", "").strip()
    role = data.get("role")  # 'student' or 'driver'

    if not message or role not in ("student", "driver"):
        return jsonify({"error": "Invalid data"}), 400

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row

    users = conn.execute(
        "SELECT id FROM users WHERE role = ?",
        (role,)
    ).fetchall()

    for u in users:
        conn.execute("""
            INSERT INTO student_notifications (user_id, title, message)
            VALUES (?, ?, ?)
        """, (u["id"], "📢 Admin Announcement", message))

    conn.commit()
    return jsonify({"sent": len(users)})


# ================= STUDENT GET ADMIN MESSAGES =================
@app.route("/student/admin_messages")
def student_admin_messages():
    if session.get("role") != "student":
        return jsonify([])

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row

    # 🔥 DELETE admin messages older than 12 hours
    conn.execute("""
        DELETE FROM student_notifications
        WHERE created_at < DATETIME('now', '-12 hours')
    """)
    conn.commit()

    # fetch remaining messages
    msgs = conn.execute("""
        SELECT message, created_at
        FROM student_notifications
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (session["user_id"],)).fetchall()

    return jsonify([dict(m) for m in msgs])
# ================= DRIVER GET ADMIN MESSAGES =================
@app.route("/driver/admin_messages")
def driver_admin_messages():
    if session.get("role") != "driver":
        return jsonify([])

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row

    # delete admin messages older than 12 hours
    conn.execute("""
        DELETE FROM student_notifications
        WHERE created_at < DATETIME('now', '-12 hours')
    """)
    conn.commit()

    msgs = conn.execute("""
        SELECT message, created_at
        FROM student_notifications
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (session["user_id"],)).fetchall()

    return jsonify([dict(m) for m in msgs])
# ================= ADMIN GET ADMIN MESSAGES =================
@app.route("/admin_messages")
def admin_messages():
    # only student & driver can see admin messages
    if session.get("role") not in ("student", "driver"):
        return jsonify([])

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row

    # delete admin messages older than 12 hours
    conn.execute("""
        DELETE FROM student_notifications
        WHERE created_at < DATETIME('now', '-12 hours')
    """)
    conn.commit()

    # fetch messages for logged-in user
    msgs = conn.execute("""
        SELECT message, created_at
        FROM student_notifications
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (session["user_id"],)).fetchall()

    return jsonify([dict(m) for m in msgs])

# ================= ADMIN DELETE COMPLAINT =================
@app.route("/admin/delete_complaint/<int:complaint_id>", methods=["POST"])
def delete_complaint(complaint_id):
    # 🔐 Only admin can delete
    if session.get("role") != "admin":
        return "Unauthorized", 403

    conn = get_db_connection()

    # 🗑️ Delete complaint
    conn.execute(
        "DELETE FROM complaints WHERE id = ?",
        (complaint_id,)
    )

    conn.commit()
    conn.close()

    flash("Complaint deleted successfully")
    return redirect(url_for("admin_complaints"))
def send_notification(user_id, notif_type, message):
    conn = get_db_connection()

    # 🚫 prevent duplicate notification
    exists = conn.execute("""
        SELECT 1 FROM notifications
        WHERE user_id = ? AND type = ?
    """, (user_id, notif_type)).fetchone()

    if not exists:
        conn.execute("""
            INSERT INTO notifications (user_id, type, message)
            VALUES (?, ?, ?)
        """, (user_id, notif_type, message))
        conn.commit()

    conn.close()
# ================= STUDENT NOTIFICATIONS PAGE =================
@app.route("/student/notifications")
def student_notifications():
    if session.get("role") != "student":
        return redirect(url_for("dashboard"))

    conn = get_db_connection()
    notes = conn.execute("""
        SELECT message, created_at, is_read
        FROM notifications
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (session["user_id"],)).fetchall()
    conn.close()

    return render_template(
        "student_notifications.html",
        notifications=notes
    )
# ================= MARK STUDENT NOTIFICATIONS AS READ =================
@app.route("/student/notifications/read")
def mark_notifications_read():
    if session.get("role") != "student":
        return redirect(url_for("dashboard"))

    conn = get_db_connection()
    conn.execute("""
        UPDATE notifications
        SET is_read = 1
        WHERE user_id = ?
    """, (session["user_id"],))
    conn.commit()
    conn.close()

    return redirect(url_for("student_notifications"))

# ================= STUDENT DASHBOARD STATUS =================
@app.route("/student/dashboard_status")
def student_dashboard_status():

    if session.get("role") != "student":
        return jsonify({})

    conn = get_db_connection()

    # get pickup
    pickup = conn.execute("""
        SELECT latitude, longitude, bus_id
        FROM pickup_points
        WHERE user_id = ?
    """, (session["user_id"],)).fetchone()

    if not pickup:
        conn.close()
        return jsonify({})

    # get latest bus location
    bus = conn.execute("""
        SELECT latitude, longitude
        FROM bus_location
        WHERE bus_id = ?
        ORDER BY updated_at DESC
        LIMIT 1
    """, (pickup["bus_id"],)).fetchone()

    if not bus:
        conn.close()
        return jsonify({})

    d_pickup = haversine(
        bus["latitude"], bus["longitude"],
        pickup["latitude"], pickup["longitude"]
    )

    conn.close()

    # 🔔 logic
    if d_pickup <= 500 and d_pickup > 150:
        return jsonify({
            "show": True,
            "message": "🚌 Bus is near your pickup point. Please be ready."
        })

    # ❌ crossed / reached pickup → hide message
    return jsonify({"show": False})

# ================= RESET TEMP BUS IF EXPIRED =================


# ================= APP RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)





