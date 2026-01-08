from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "smart_bus_secret"

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
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        try:
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                (username, email, password)
            )
            conn.commit()
            conn.close()

            flash("✅ Signup successful. Please login.")
            return redirect(url_for("index"))

        except sqlite3.IntegrityError:
            flash("❌ Username or Email already exists")

    return render_template("signup.html")


@app.route("/login", methods=["POST"])
def login():
    user_input = request.form["login_user"]
    password = request.form["login_password"]

    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE (username=? OR email=?) AND password=?",
        (user_input, user_input, password)
    ).fetchone()
    conn.close()

    if user:
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]   # ✅ ADD THIS LINE
        return redirect(url_for("dashboard"))


    flash("❌ Invalid login credentials")
    return redirect(url_for("index"))


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
    user = conn.execute(
        "SELECT bus_id FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    bus = None
    if user and user["bus_id"]:
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
        pickup=pickup
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

    if "user_id" not in session or session.get("role") != "driver":
        return jsonify({"error": "unauthorized"}), 403

    data = request.json
    lat = data.get("latitude")
    lng = data.get("longitude")

    if not lat or not lng:
        return jsonify({"error": "invalid data"}), 400

    conn = get_db_connection()

    # get driver's bus
    bus = conn.execute("""
        SELECT bus_id FROM users WHERE id = ?
    """, (session["user_id"],)).fetchone()

    if not bus or not bus["bus_id"]:
        conn.close()
        return jsonify({"error": "no bus assigned"}), 400

    conn.execute("""
        INSERT INTO driver_location (driver_id, bus_id, latitude, longitude)
        VALUES (?, ?, ?, ?)
    """, (session["user_id"], bus["bus_id"], lat, lng))

    conn.commit()
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
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        admin = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=? AND role='admin'",
            (username, password)
        ).fetchone()
        conn.close()

        if admin:
            session.clear()                 # 🔑 VERY IMPORTANT
            session["user_id"] = admin["id"]
            session["username"] = admin["username"]
            session["role"] = "admin"

            return redirect(url_for("admin_dashboard"))
        else:
            flash("❌ Invalid admin credentials")

    return render_template("admin_login.html")


@app.route("/admin/dashboard")
def admin_dashboard():
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("admin_login"))

    # ✅ ADD THIS PART
    conn = get_db_connection()

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

    conn.close()

    # ✅ PASS DATA TO TEMPLATE
    return render_template(
        "admin_dashboard.html",
        total_students=total_students,
        total_drivers=total_drivers,
        total_buses=total_buses,
        active_tracking=active_tracking
    )





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
    if "admin" not in session:
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
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        bus_id = request.form["bus_id"]

        # ❗ check duplicate
        existing = conn.execute(
            "SELECT id FROM users WHERE username=?",
            (username,)
        ).fetchone()

        if existing:
            conn.close()
            flash("❌ Username already exists")
            return redirect(url_for("admin_add_driver"))

        # 1️⃣ create driver user
        conn.execute("""
            INSERT INTO users (username, email, password, role, bus_id)
            VALUES (?, ?, ?, 'driver', ?)
        """, (username, email, password, bus_id))

        driver_user_id = conn.execute(
            "SELECT id FROM users WHERE username=?",
            (username,)
        ).fetchone()["id"]

        # 2️⃣ map driver to bus
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





@app.route("/driver/update_location", methods=["POST"])
def update_driver_location():
    if session.get("role") != "driver":
        return "Unauthorized", 403

    lat = request.form.get("lat")
    lng = request.form.get("lng")
    driver_id = session["user_id"]

    conn = get_db_connection()

    conn.execute("""
        INSERT INTO driver_location (driver_id, latitude, longitude)
        VALUES (?, ?, ?)
        ON CONFLICT(driver_id) DO UPDATE SET
        latitude=excluded.latitude,
        longitude=excluded.longitude,
        updated_at=CURRENT_TIMESTAMP
    """, (driver_id, lat, lng))

    conn.commit()
    conn.close()

    return "OK"

@app.route("/student/get_location")
def student_get_location():

    if "user_id" not in session:
        return jsonify({})

    conn = get_db_connection()

    user = conn.execute(
        "SELECT bus_id FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    if not user or not user["bus_id"]:
        conn.close()
        return jsonify({})

    loc = conn.execute("""
        SELECT latitude, longitude
        FROM bus_location
        WHERE bus_id = ?
        ORDER BY updated_at DESC
        LIMIT 1
    """, (user["bus_id"],)).fetchone()

    conn.close()

    if loc:
        return jsonify({
            "latitude": loc["latitude"],
            "longitude": loc["longitude"]
        })

    return jsonify({})







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

    bus = conn.execute(
        "SELECT bus_id FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    if not bus or not bus["bus_id"]:
        conn.close()
        return jsonify([])

    pickups = conn.execute("""
        SELECT latitude, longitude, pickup_name
        FROM pickup_points
        WHERE bus_id = ?
    """, (bus["bus_id"],)).fetchall()

    conn.close()

    return jsonify([
        {
            "lat": p["latitude"],
            "lng": p["longitude"],
            "name": p["pickup_name"]
        } for p in pickups
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
        "SELECT bus_id FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    if not user or not user["bus_id"]:
        conn.close()
        return jsonify([])

    pickups = conn.execute("""
        SELECT pickup_name, latitude, longitude
        FROM pickup_points
        WHERE bus_id = ?
    """, (user["bus_id"],)).fetchall()

    conn.close()

    return jsonify([
        {
            "name": p["pickup_name"],
            "lat": p["latitude"],
            "lng": p["longitude"]
        } for p in pickups
    ])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)


