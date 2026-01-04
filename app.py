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
        (1, 1, '+91-9876543210'),
        (2, 1, '+91-9123456780'),
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


@app.route("/my_bus")
def my_bus():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    user = conn.execute(
        "SELECT bus_id FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    bus = None
    if user and user["bus_id"]:
        bus = conn.execute(
            "SELECT * FROM buses WHERE id = ?",
            (user["bus_id"],)
        ).fetchone()

    buses = conn.execute("SELECT * FROM buses").fetchall()

    conn.close()

    return render_template(
        "my_bus.html",
        bus=bus,
        buses=buses
    )


# ================= DRIVER GPS PAGE (✅ ADDED) =================
@app.route("/driver_gps")
def driver_gps():

    if "user_id" not in session:
        return redirect(url_for("index"))

    # 🔒 Allow ONLY drivers
    if session.get("role") != "driver":
        flash("❌ Access denied: Drivers only")
        return redirect(url_for("dashboard"))

    conn = get_db_connection()

    driver = conn.execute("""
        SELECT buses.*
        FROM drivers
        JOIN buses ON drivers.bus_id = buses.id
        WHERE drivers.user_id = ?
    """, (session["user_id"],)).fetchone()

    conn.close()

    if not driver:
        flash("❌ No bus assigned to you")
        return redirect(url_for("dashboard"))

    return render_template("driver_gps.html", bus=driver)



# ================= GPS UPDATE (DRIVER) =================
@app.route("/update_location", methods=["POST"])
def update_location():

    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    # 🔒 Only drivers can send GPS
    if session.get("role") != "driver":
        return jsonify({"error": "Drivers only"}), 403

    data = request.get_json()
    latitude = data.get("latitude")
    longitude = data.get("longitude")

    conn = get_db_connection()

    driver = conn.execute(
        "SELECT bus_id FROM drivers WHERE user_id=?",
        (session["user_id"],)
    ).fetchone()

    if not driver:
        conn.close()
        return jsonify({"error": "No bus assigned"}), 403

    conn.execute("""
        INSERT INTO bus_location (bus_id, latitude, longitude)
        VALUES (?, ?, ?)
    """, (driver["bus_id"], latitude, longitude))

    conn.commit()
    conn.close()

    return jsonify({"status": "Location updated"})



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

    return render_template("admin_dashboard.html")




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

    # 🔒 Admin protection
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

        # 1️⃣ Create user as driver
        conn.execute("""
            INSERT INTO users (username, email, password, role)
            VALUES (?, ?, ?, 'driver')
        """, (username, email, password))

        driver_user_id = conn.execute(
            "SELECT id FROM users WHERE username=?",
            (username,)
        ).fetchone()[0]

        # 2️⃣ Assign bus to driver
        conn.execute("""
            INSERT INTO drivers (user_id, bus_id)
            VALUES (?, ?)
        """, (driver_user_id, bus_id))

        conn.commit()
        conn.close()

        flash("✅ Driver created and bus assigned")
        return redirect(url_for("admin"))

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
    if "user_id" not in session or session.get("role") != "student":
        return redirect(url_for("index"))

    conn = get_db_connection()

    existing = conn.execute(
        "SELECT * FROM pickup_points WHERE user_id=?",
        (session["user_id"],)
    ).fetchone()

    if request.method == "POST":
        pickup_name = request.form["pickup_name"]
        lat = request.form["latitude"]
        lng = request.form["longitude"]

        if existing:
            conn.execute("""
                UPDATE pickup_points
                SET pickup_name=?, latitude=?, longitude=?
                WHERE user_id=?
            """, (pickup_name, lat, lng, session["user_id"]))
        else:
            conn.execute("""
                INSERT INTO pickup_points (user_id, pickup_name, latitude, longitude)
                VALUES (?, ?, ?, ?)
            """, (session["user_id"], pickup_name, lat, lng))

        conn.commit()
        conn.close()

        flash("✅ Pickup point saved successfully")
        return redirect(url_for("dashboard"))

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






# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)


