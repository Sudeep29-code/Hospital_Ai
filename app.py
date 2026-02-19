from flask import Flask, render_template, request, redirect, session, send_file, url_for
from scipy.optimize import linear_sum_assignment
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import os
import random
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

import joblib
import numpy as np
import shap
from statsmodels.tsa.arima.model import ARIMA
import json
from flask import flash



# ========================
# RL Q-LEARNING SETTINGS
# ========================

Q_TABLE_FILE = "q_table.json"
ACTIONS = ["increase_fairness", "increase_wait", "balance"]
ALPHA = 0.1      # learning rate
GAMMA = 0.9      # discount factor
EPSILON = 0.2    # exploration rate




# ReportLab Imports
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4

app = Flask(__name__)
app.secret_key = "supersecretkey123"

# ====== DECORATORS ======
def admin_required(f):
    def wrapper(*args, **kwargs):
        if "admin_id" not in session:
            return redirect("/admin/login")
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper



# Admin login

@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM admins WHERE username=%s", (username,))
        admin = cursor.fetchone()

        cursor.close()
        conn.close()

        if admin and check_password_hash(admin["password_hash"], password):
            session["admin_id"] = admin["id"]
            return redirect("/admin/dashboard")

        return "Invalid credentials"

    return render_template("admin/login.html")


# Admin Dashboard
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    optimized = request.args.get("optimized")

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # Total patients
    cursor.execute("SELECT COUNT(*) AS total_patients FROM patients")
    total_patients = cursor.fetchone()["total_patients"]

    # Total doctors
    cursor.execute("SELECT COUNT(*) AS total_doctors FROM doctors")
    total_doctors = cursor.fetchone()["total_doctors"]

    # Average wait time
    cursor.execute("SELECT AVG(predicted_delay) AS avg_wait FROM patients")
    result = cursor.fetchone()
    avg_wait = result["avg_wait"] if result["avg_wait"] else 0

    # Overloaded departments (more than 5 waiting patients)
    cursor.execute("""
        SELECT department, COUNT(*) AS count
        FROM patients
        WHERE status = 'waiting'
        GROUP BY department
        HAVING COUNT(*) > 5
    """)
    overloaded = cursor.fetchall()

    # AI Settings
    cursor.execute("SELECT fairness_weight, wait_weight FROM ai_settings WHERE id = 1")
    settings = cursor.fetchone()

    # Department patient distribution (for chart)
    cursor.execute("""
        SELECT department, COUNT(*) AS count
        FROM patients
        WHERE status = 'waiting'
        GROUP BY department
    """)
    dept_data = cursor.fetchall()

    departments = [d["department"] for d in dept_data]
    counts = [d["count"] for d in dept_data]
    # 🔮 Forecast Next Hour Arrivals
    forecast_data = {}

    for dept in departments:
        forecast_data[dept] = forecast_next_hour(dept)


    # Doctor Management Data
    cursor.execute("""
        SELECT 
            d.id,
            d.name,
            d.department,
            d.available_from,
            d.available_to,
            d.is_active,
            COUNT(p.id) AS current_load,
            SUM(CASE 
                WHEN p.status = 'Completed'
                AND DATE(p.completed_at) = CURDATE()
                THEN 1 ELSE 0 
            END) AS today_completed
        FROM doctors d
        LEFT JOIN patients p 
            ON p.doctor_id = d.id
            AND p.status IN ('waiting','emergency')
        GROUP BY d.id
    """)
    
    doctors = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin/dashboard.html",
        total_patients=total_patients,
        total_doctors=total_doctors,
        avg_wait=round(avg_wait, 2),
        overloaded=overloaded,
        settings=settings,
        optimized=optimized,
        departments=departments,
        counts=counts,
        doctors=doctors,
        forecast_data=forecast_data
    )



@app.route("/admin/add-doctor", methods=["GET", "POST"])
def add_doctor():
    if request.method == "POST":
        try:
            name = request.form.get("name")
            department = request.form.get("department")
            password = request.form.get("password")
            available_from = request.form.get("available_from")
            available_to = request.form.get("available_to")

            conn = get_db()
            cursor = conn.cursor()

            # 1️⃣ Insert doctor first (without doctor_code)
            insert_query = """
                INSERT INTO doctors 
                (name, department, password, available_from, available_to)
                VALUES (%s, %s, %s, %s, %s)
            """

            cursor.execute(insert_query, 
                (name, department, password, available_from, available_to)
            )
            conn.commit()

            # 2️⃣ Get the auto-generated ID
            doctor_id = cursor.lastrowid

            # 3️⃣ Generate code like DOC001
            doctor_code = f"DOC{str(doctor_id).zfill(3)}"

            # 4️⃣ Update doctor with generated code
            update_query = """
                UPDATE doctors
                SET doctor_code = %s
                WHERE id = %s
            """

            cursor.execute(update_query, (doctor_code, doctor_id))
            conn.commit()

            cursor.close()
            conn.close()

            return render_template(
                "admin/doctor_success.html",
                doctor_code=doctor_code,
                password=password,
                name=name
            )

        except Exception as e:
            return f"Error: {e}"

    return render_template("admin/add_doctor.html")









# Edit Doctor
@app.route("/admin/edit-doctor/<int:doctor_id>", methods=["GET", "POST"])
@admin_required
def edit_doctor(doctor_id):

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form["name"]
        department = request.form["department"]
        available_from = request.form["available_from"]
        available_to = request.form["available_to"]

        cursor.execute("""
            UPDATE doctors
            SET name=%s,
                department=%s,
                available_from=%s,
                available_to=%s
            WHERE id=%s
        """, (name, department, available_from, available_to, doctor_id))

        conn.commit()
        cursor.close()
        conn.close()

        return redirect("/admin/dashboard")

    cursor.execute("SELECT * FROM doctors WHERE id=%s", (doctor_id,))
    doctor = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("admin/edit_doctor.html", doctor=doctor)


# Activate/Deactivate Doctor
@app.route("/admin/toggle-doctor/<int:doctor_id>")
@admin_required
def toggle_doctor(doctor_id):

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT is_active FROM doctors WHERE id=%s", (doctor_id,))
    doctor = cursor.fetchone()

    new_status = 0 if doctor["is_active"] == 1 else 1

    cursor.execute("""
        UPDATE doctors
        SET is_active=%s
        WHERE id=%s
    """, (new_status, doctor_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect("/admin/dashboard")
# Delete Doctor
@app.route("/admin/delete-doctor/<int:doctor_id>")
@admin_required
def delete_doctor(doctor_id):
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE doctors
            SET is_active = 0
            WHERE id = %s
        """, (doctor_id,))
        conn.commit()
        flash("Doctor deactivated successfully.", "success")

    except Exception as e:
        conn.rollback()
        flash("Error while deactivating doctor.", "danger")

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("admin_dashboard"))









@app.route("/admin/force-optimize")
@admin_required
def force_optimize():

    run_global_optimization()   # your main optimization function

    return redirect(url_for("admin_dashboard", optimized="1"))


@app.route("/admin/assignment-explanations")
@admin_required
def assignment_explanations():

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT ae.*, p.name AS patient_name, d.name AS doctor_name
        FROM assignment_explanations ae
        JOIN patients p ON ae.patient_id = p.id
        JOIN doctors d ON ae.doctor_id = d.id
        ORDER BY ae.created_at DESC
        LIMIT 20
    """)

    data = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("admin/assignment_explanation.html",
        assignments=data
    )





# Admin logout
@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    return redirect("/admin/login")

# Admin ai control
@app.route("/admin/ai-control", methods=["GET", "POST"])
@admin_required
def ai_control():

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        fairness = float(request.form["fairness_weight"])
        wait = float(request.form["wait_weight"])
        # Ensure weights sum to 1
        if fairness + wait != 1.0:
            return "Fairness weight + Wait weight must equal 1.0"
        overload = int(request.form["overload_threshold"])
        cooldown = int(request.form["cooldown_minutes"])

        cursor.execute("""
            UPDATE ai_settings
            SET fairness_weight=%s,
                wait_weight=%s,
                overload_threshold=%s,
                cooldown_minutes=%s
            WHERE id=1
        """, (fairness, wait, overload, cooldown))

        conn.commit()

    cursor.execute("SELECT * FROM ai_settings WHERE id=1")
    settings = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("admin/ai_control.html", settings=settings)



# ========================
# Load AI Model
# ========================
model = joblib.load("duration_model.pkl")
le_dept = joblib.load("dept_encoder.pkl")
le_priority = joblib.load("priority_encoder.pkl")
le_disease = joblib.load("disease_encoder.pkl")

# 🔥 Load No-Show Model
no_show_model = joblib.load("no_show_model.pkl")
no_show_le_dept = joblib.load("no_show_dept_encoder.pkl")
no_show_le_priority = joblib.load("no_show_priority_encoder.pkl")

# ========================
# SHAP Explainers (Correct Type)
# ========================

# Duration model (if RandomForest or similar)
duration_explainer = shap.TreeExplainer(model)

# No-show model (Logistic Regression)
no_show_explainer = shap.LinearExplainer(no_show_model, np.zeros((1,4)))






# ========================
# Priority Logic
# ========================
def calculate_priority(age, oxygen, temp, bp, disease):

    disease = disease.lower()
    emergency_diseases = ["stroke", "heart attack", "trauma", "sepsis"]

    # -------------------------
    # PEDIATRIC CASE (<18)
    # -------------------------
    if age < 18:

        if oxygen < 90 or temp >= 38.5 or bp < 70 or bp > 140:
            return "HIGH"

        elif 90 <= oxygen < 94 or 37.6 <= temp < 38.5:
            return "MEDIUM"

        else:
            return "LOW"

    # -------------------------
    # ADULT CASE (>=18)
    # -------------------------
    else:

        if (
            oxygen < 85 or
            temp >= 39.5 or
            bp >= 180 or
            bp < 90 or
            any(d in disease for d in emergency_diseases)
        ):
            return "HIGH"

        elif (
            85 <= oxygen < 92 or
            38.5 <= temp < 39.5 or
            140 <= bp < 180
        ):
            return "MEDIUM"

        else:
            return "LOW"


# ========================
# Database Connection
# ========================
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="kaibalya123",
        database="hospital_db"
    )

# ========================
# TIME SERIES FORECASTING
# ========================

def get_hourly_arrivals(department, hours=48):

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            DATE_FORMAT(created_at, '%Y-%m-%d %H:00:00') AS hour_slot,
            COUNT(*) AS count
        FROM patients
        WHERE department = %s
        AND created_at >= NOW() - INTERVAL %s HOUR
        GROUP BY hour_slot
        ORDER BY hour_slot ASC
    """, (department, hours))

    data = cursor.fetchall()

    cursor.close()
    conn.close()

    return data


def forecast_moving_average(department):

    data = get_hourly_arrivals(department)

    if len(data) < 3:
        return 0

    counts = [d["count"] for d in data]

    forecast = sum(counts[-3:]) / 3

    return round(forecast, 2)


def forecast_arima(department):

    data = get_hourly_arrivals(department)

    if len(data) < 6:
        return forecast_moving_average(department)

    try:
        counts = [d["count"] for d in data]

        model = ARIMA(counts, order=(1,1,1))
        model_fit = model.fit()

        forecast = model_fit.forecast(steps=1)

        return round(float(forecast[0]), 2)

    except Exception as e:
        print("ARIMA error:", e)
        return forecast_moving_average(department)


def forecast_next_hour(department):

    ma_forecast = forecast_moving_average(department)
    arima_forecast = forecast_arima(department)

    final_forecast = (ma_forecast * 0.4) + (arima_forecast * 0.6)

    return round(final_forecast, 2)



# ========================
# Q-TABLE FUNCTIONS
# ========================

def load_q_table():
    try:
        with open(Q_TABLE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_q_table(q_table):
    with open(Q_TABLE_FILE, "w") as f:
        json.dump(q_table, f)


def get_system_state(department):

    forecast = forecast_next_hour(department)

    if forecast < 5:
        load_state = "low"
    elif forecast < 15:
        load_state = "medium"
    else:
        load_state = "high"

    return load_state


def choose_action(state):

    q_table = load_q_table()

    if random.uniform(0,1) < EPSILON:
        return random.choice(ACTIONS)

    if state not in q_table:
        q_table[state] = {a: 0 for a in ACTIONS}
        save_q_table(q_table)

    return max(q_table[state], key=q_table[state].get)

def update_q_table(state, action, reward, next_state):

    q_table = load_q_table()

    if state not in q_table:
        q_table[state] = {a: 0 for a in ACTIONS}

    if next_state not in q_table:
        q_table[next_state] = {a: 0 for a in ACTIONS}

    current_q = q_table[state][action]
    max_future_q = max(q_table[next_state].values())

    new_q = current_q + ALPHA * (reward + GAMMA * max_future_q - current_q)

    q_table[state][action] = new_q

    save_q_table(q_table)


def generate_doctor_code(department):
    prefix_map = {
        "General Medicine": "GM",
        "Cardiology": "CR",
        "Neurology": "NE",
        "Orthopedics": "OR",
        "Pediatrics": "PD"
    }

    prefix = prefix_map.get(department, "DR")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) FROM doctors WHERE department=%s
    """, (department,))

    count = cursor.fetchone()[0] + 1

    cursor.close()
    conn.close()

    return f"{prefix}{str(count).zfill(3)}"

# ========================
# AI Duration Prediction
# ========================
def predict_duration(age, oxygen, bp, temperature, department, priority, disease):
    try:
        department = department.strip()
        priority = priority.strip()
        disease = disease.strip().lower()

        dept_encoded = le_dept.transform([department])[0] if department in le_dept.classes_ else 0
        priority_encoded = le_priority.transform([priority])[0] if priority in le_priority.classes_ else 0
        disease_encoded = le_disease.transform([disease])[0] if disease in le_disease.classes_ else 0

        features = np.array([[age, oxygen, bp, temperature,
                              dept_encoded, priority_encoded, disease_encoded]])

        prediction = model.predict(features)[0]

        # ========================
        # 🔥 SHAP Explanation
        # ========================
        shap_values = duration_explainer(features)

        feature_names = [
            "Age",
            "Oxygen Level",
            "Blood Pressure",
            "Temperature",
            "Department",
            "Priority",
            "Disease"
        ]

        explanation = []

        for name, value in zip(feature_names, shap_values.values[0]):
            if abs(value) > 1:
                explanation.append(f"{name} contributed {round(value,2)} minutes")

        return round(float(prediction), 2), explanation

    except Exception as e:
        print("Duration Prediction Error:", e)
        return 10, ["Fallback prediction used"]




# ========================
# AI No-Show Prediction
# ========================
def predict_no_show(age, priority, department, predicted_duration):
    try:
        department = department.strip()
        priority = priority.strip()

        dept_encoded = (
            no_show_le_dept.transform([department])[0]
            if department in no_show_le_dept.classes_
            else 0
        )

        priority_encoded = (
            no_show_le_priority.transform([priority])[0]
            if priority in no_show_le_priority.classes_
            else 0
        )

        features = np.array([[age, dept_encoded, priority_encoded, predicted_duration]])

        probability = no_show_model.predict_proba(features)[0][1]

        # ========================
        # 🔥 SHAP Explanation
        # ========================
        shap_values = no_show_explainer(features)

        feature_names = [
            "Age",
            "Department",
            "Priority",
            "Predicted Duration"
        ]

        explanation = []

        for name, value in zip(feature_names, shap_values.values[0]):
            if abs(value) > 0.02:
                direction = "increased" if value > 0 else "reduced"
                explanation.append(
                    f"{name} {direction} no-show risk by {round(abs(value)*100,2)}%"
                )

        return round(float(probability), 2), explanation

    except Exception as e:
        print("No-Show Prediction Error:", e)
        return 0.10, ["Fallback probability used"]




# ========================
# Home Page
# ========================
@app.route("/")
def home():
    return render_template("index.html")

# doctor login
@app.route("/doctor_login", methods=["GET", "POST"])
def doctor_login():

    if request.method == "POST":

        doctor_id = request.form["doctor_id"]
        password = request.form["password"]

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM doctors WHERE doctor_code=%s", (doctor_id,))
        doctor = cursor.fetchone()

        cursor.close()
        conn.close()

        if doctor and doctor["password"] == password:

            session["doctor_id"] = doctor["id"]
            session["doctor_name"] = doctor["name"]
            session["department"] = doctor["department"]   # 🔥 THIS WAS MISSING

            return redirect("/doctor_dashboard")

        else:
            return "Invalid ID or Password"

    return render_template("doctor_login.html")

# Forgot password
@app.route("/doctor/doctor_forgot_password", methods=["GET", "POST"])
def doctor_forgot_password():
    message = None

    if request.method == "POST":
        doctor_code = request.form.get("doctor_code")
        new_password = request.form.get("new_password")

        conn = get_db()
        cursor = conn.cursor()

        query = "UPDATE doctors SET password=%s WHERE doctor_code=%s"
        cursor.execute(query, (new_password, doctor_code))
        conn.commit()

        cursor.close()
        conn.close()

        message = "Password Updated Successfully!"

    return render_template("doctor/forgot_password.html", message=message)


# ========================
# Automatic Reassignment Engine
# ========================
def auto_reassign_patients(department):

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT id
        FROM doctors
        WHERE department=%s
    """, (department,))

    doctors = cursor.fetchall()

    if len(doctors) < 2:
        cursor.close()
        conn.close()
        return

    doctor_load = {}

    for doc in doctors:
        cursor.execute("""
            SELECT COUNT(*) AS active_count
            FROM patients
            WHERE doctor_id=%s
            AND status IN ('waiting','emergency')
        """, (doc["id"],))

        doctor_load[doc["id"]] = cursor.fetchone()["active_count"]

    highest_doc = max(doctor_load, key=doctor_load.get)
    lowest_doc = min(doctor_load, key=doctor_load.get)

    current_score = calculate_department_score(department)

    if doctor_load[highest_doc] - doctor_load[lowest_doc] >= 1:

        # simulate shift
        doctor_load[highest_doc] -= 1
        doctor_load[lowest_doc] += 1

        simulated_score = calculate_department_score(department)

        # revert simulation
        doctor_load[highest_doc] += 1
        doctor_load[lowest_doc] -= 1

        if simulated_score <= current_score:
            return  # do NOT shift if it doesn't improve system


        cursor.execute("""
        SELECT id, name, no_show_probability, last_reassigned_at
        FROM patients
        WHERE doctor_id=%s
        AND priority='LOW'
        AND status='waiting'
        AND no_show_probability < 0.25
        ORDER BY no_show_probability ASC
        """, (highest_doc,))

        patients = cursor.fetchall()

        from datetime import datetime, timedelta
        cooldown = timedelta(minutes=5)

        patient = None

        for p in patients:
            last_time = p["last_reassigned_at"]

            if last_time:
                if datetime.now() - last_time < cooldown:
                    continue  # Skip recently shifted patient

            patient = p
            break


        if patient:

            # 🔥 Shift patient
            cursor.execute("""
            UPDATE patients
            SET doctor_id=%s,
                last_reassigned_at=%s
            WHERE id=%s
            """, (lowest_doc, datetime.now(), patient["id"]))


            # 🔥 Store explanation log
            reason = (
                f"Patient {patient['name']} shifted "
                f"from Doctor {highest_doc} "
                f"to Doctor {lowest_doc} "
                f"due to load imbalance "
                f"({doctor_load[highest_doc]} vs {doctor_load[lowest_doc]} patients)"
            )

            cursor.execute("""
                INSERT INTO reassignment_logs
                (department, patient_id, from_doctor, to_doctor, reason)
                VALUES (%s,%s,%s,%s,%s)
            """, (
                department,
                patient["id"],
                highest_doc,
                lowest_doc,
                reason
            ))

    conn.commit()
    cursor.close()
    conn.close()

# ========================
# Fairness Calculation
# ========================
def calculate_fairness(department):

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT id FROM doctors
        WHERE department=%s
    """, (department,))

    doctors = cursor.fetchall()

    loads = []

    for doc in doctors:
        cursor.execute("""
            SELECT COUNT(*) AS active_count
            FROM patients
            WHERE doctor_id=%s
            AND status IN ('waiting','emergency')
        """, (doc["id"],))

        loads.append(cursor.fetchone()["active_count"])

    cursor.close()
    conn.close()

    if not loads:
        return 0

    return max(loads) - min(loads)



# =========================
# Multi-Objective Score
# =========================
def calculate_department_score(department):

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT doctor_id, COUNT(*) AS total
        FROM patients
        WHERE status IN ('waiting','emergency')
        AND department=%s
        GROUP BY doctor_id
    """, (department,))

    data = cursor.fetchall()

    if not data:
        return 100

    loads = [d["total"] for d in data]

    max_load = max(loads)
    min_load = min(loads)

    imbalance = max_load - min_load

    avg_load = sum(loads) / len(loads)

    # Score components
    fairness_component = max(0, 100 - (imbalance * 10))
    utilization_component = max(0, 100 - abs(avg_load - 5) * 10)

    final_score = (0.6 * fairness_component) + (0.4 * utilization_component)

    cursor.close()
    conn.close()

    return round(final_score, 2)

# ========================
# AI Optimization Score
# ========================
def calculate_optimization_score(department):

    fairness = calculate_fairness(department)

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT * FROM patients
        WHERE department=%s
        AND status IN ('waiting','emergency')
    """, (department,))

    patients = cursor.fetchall()

    cursor.close()
    conn.close()

    if not patients:
        return 100

    total_wait = 0

    for p in patients:
        predicted,_= predict_duration(
            p["age"],
            p["oxygen"],
            p["bp"],
            p["temperature"],
            p["department"],
            p["priority"],
            p["disease"]
        )
        total_wait += predicted

    avg_wait = total_wait / len(patients)

    # Normalize fairness (0–10 scale)
    fairness_score = max(0, 100 - fairness * 15)

    future_load = forecast_next_hour(department)
    future_penalty = future_load * 2

    wait_score = max(0, 100 - avg_wait - future_penalty)


    # 🔥 Multi-objective weighted optimization
    # Load dynamic weights
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT fairness_weight, wait_weight FROM ai_settings WHERE id=1")
    settings = cursor.fetchone()

    cursor.close()
    conn.close()

    fairness_weight = settings["fairness_weight"]
    wait_weight = settings["wait_weight"]

    final_score = fairness_weight * fairness_score + wait_weight * wait_score


    return round(final_score, 2)

# ========================
# GRAPH-BASED OPTIMIZER
# ========================
def optimize_assignments_graph(department):

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # ========================
    # GET WAITING + EMERGENCY PATIENTS
    # ========================
    cursor.execute("""
        SELECT * FROM patients
        WHERE department=%s
        AND status IN ('waiting','emergency')
    """, (department,))
    patients = cursor.fetchall()

    # ========================
    # GET ACTIVE DOCTORS
    # ========================
    cursor.execute("""
        SELECT * FROM doctors
        WHERE department=%s
        AND is_active=1
    """, (department,))
    doctors = cursor.fetchall()

    # ========================
    # SAFETY CHECK
    # ========================
    if not patients or not doctors:
        cursor.close()
        conn.close()
        return

    # ========================
    # PRE-CALCULATE DOCTOR LOADS (PERFORMANCE FIX)
    # ========================
    doctor_loads = {}

    cursor.execute("""
        SELECT doctor_id, COUNT(*) AS doctor_load
        FROM patients
        WHERE department=%s
        AND status IN ('waiting','emergency')
        GROUP BY doctor_id
    """, (department,))

    load_data = cursor.fetchall()

    # Initialize all doctors to 0 load
    for d in doctors:
        doctor_loads[d["id"]] = 0

    # Update with actual loads
    for row in load_data:
        doctor_loads[row["doctor_id"]] = row["doctor_load"]

    import numpy as np
    from scipy.optimize import linear_sum_assignment

    # ========================
    # RL DECIDES WEIGHTS
    # ========================
    state = get_system_state(department)
    action = choose_action(state)

    if action == "increase_fairness":
        fairness_weight = 0.7
        wait_weight = 0.3
    elif action == "increase_wait":
        fairness_weight = 0.3
        wait_weight = 0.7
    else:
        fairness_weight = 0.5
        wait_weight = 0.5

    # ========================
    # BUILD COST MATRIX
    # ========================
    cost_matrix = np.zeros((len(patients), len(doctors)))

    for i, p in enumerate(patients):
        for j, d in enumerate(doctors):

            # 🔥 Predicted Duration
            predicted, _ = predict_duration(
                p["age"],
                p["oxygen"],
                p["bp"],
                p["temperature"],
                p["department"],
                p["priority"],
                p["disease"]
            )

            # 🔥 No-show probability
            no_show = p.get("no_show_probability", 0.1)
            expected_time = predicted * (1 - no_show)

            # 🔥 Doctor load (NO SQL HERE — optimized)
            load = doctor_loads.get(d["id"], 0)

            # 🔥 Emergency bonus
            priority_bonus = -10 if p["priority"] == "HIGH" else 0

            cost = (wait_weight * expected_time) + (fairness_weight * load * 5) + priority_bonus

            cost_matrix[i][j] = cost

    # ========================
    # HUNGARIAN ALGORITHM
    # ========================
    row_ind, col_ind = linear_sum_assignment(cost_matrix)

    # ========================
    # APPLY ASSIGNMENTS
    # ========================
    for r, c in zip(row_ind, col_ind):

        patient = patients[r]
        doctor = doctors[c]

        patient_id = patient["id"]
        doctor_id = doctor["id"]

        # Recalculate values for explanation
        predicted, _ = predict_duration(
            patient["age"],
            patient["oxygen"],
            patient["bp"],
            patient["temperature"],
            patient["department"],
            patient["priority"],
            patient["disease"]
        )

        no_show = patient.get("no_show_probability", 0.1)
        expected_time = predicted * (1 - no_show)

        load = doctor_loads.get(doctor_id, 0)

        priority_bonus = -10 if patient["priority"] == "HIGH" else 0

        final_cost = (wait_weight * expected_time) + (fairness_weight * load * 5) + priority_bonus

        # 🔥 UPDATE PATIENT
        cursor.execute("""
            UPDATE patients
            SET doctor_id=%s
            WHERE id=%s
        """, (doctor_id, patient_id))

        # Update in-memory load
        doctor_loads[doctor_id] += 1

        # 🔥 INSERT EXPLANATION LOG
        cursor.execute("""
            INSERT INTO assignment_explanations
            (patient_id, doctor_id, department,
            predicted_duration, doctor_load,
            no_show_probability, rl_action, final_cost)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            patient_id,
            doctor_id,
            department,
            predicted,
            load,
            no_show,
            action,
            round(final_cost, 2)
        ))

    conn.commit()

    # ========================
    # RL REWARD UPDATE
    # ========================
    new_score = calculate_optimization_score(department)
    next_state = get_system_state(department)
    reward = new_score
    update_q_table(state, action, reward, next_state)

    cursor.close()
    conn.close()



# ========================
# GLOBAL OPTIMIZATION ENGINE
# ========================
def run_global_optimization():

    print("⚡ Admin triggered global optimization...")

    conn = get_db()
    cursor = conn.cursor()

    # Get all departments
    cursor.execute("SELECT DISTINCT department FROM doctors")
    departments = cursor.fetchall()

    for dept in departments:
        department = dept[0]

    predicted_arrivals = forecast_next_hour(department)

    print(f"🔮 Predicted next hour arrivals for {department}: {predicted_arrivals}")

    if predicted_arrivals > 10:
        print("⚠ Upcoming overload predicted. Pre-optimizing...")
        optimize_assignments_graph(department)

    # Still calculate optimization score
    score = calculate_optimization_score(department)
    print(f"Updated Optimization Score for {department}: {score}")


    cursor.close()
    conn.close()

# ==============================
# TRUE CONTINUOUS OPTIMIZER
# ==============================

def continuous_optimizer():
    print("Running background optimization...")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT department FROM doctors")
    departments = cursor.fetchall()

    for dept in departments:
        optimize_assignments_graph(dept[0])


    cursor.close()
    conn.close()


scheduler = BackgroundScheduler()

scheduler.add_job(
    func=continuous_optimizer,
    trigger="interval",
    seconds=20
)

if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    scheduler.start()


# DOCTOR DASHBOARD
@app.route("/doctor_dashboard")
def doctor_dashboard():

    if "doctor_id" not in session or "department" not in session:
        return redirect("/doctor_login")

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    try:
        doctor_id = int(session["doctor_id"])
    except:
        return redirect("/doctor_login")

    department = session["department"]

    print("SESSION DOCTOR ID:", doctor_id)

    # 🔥 Fetch patients assigned to this doctor
    cursor.execute("""
        SELECT *
        FROM patients
        WHERE doctor_id = %s
        AND status IN ('waiting', 'emergency')
        ORDER BY priority_score DESC, id ASC
    """, (doctor_id,))


    patients = cursor.fetchall()

    # 🔥 SPLIT PATIENTS CORRECTLY
    regular_patients = [p for p in patients if p["status"] == "waiting"]
    emergency_patients = [p for p in patients if p["status"] == "emergency"]

    # 🔥 Doctor stats
    cursor.execute("""
        SELECT total_consultation_time, patients_completed
        FROM doctors
        WHERE id = %s
    """, (doctor_id,))

    doc = cursor.fetchone()

    if not doc:
        cursor.close()
        conn.close()
        return "Doctor not found."

    total_time = doc.get("total_consultation_time", 0) or 0
    completed = doc.get("patients_completed", 0) or 0

    avg_time = total_time / completed if completed > 0 else 0

    shift_minutes = 480
    utilization = (total_time / shift_minutes) * 100 if shift_minutes > 0 else 0
    utilization = min(utilization, 100)

    # 🔥 Department waiting count
    cursor.execute("""
        SELECT COUNT(*) AS total_waiting
        FROM patients
        WHERE department = %s
        AND status = 'waiting'
    """, (department,))

    waiting_data = cursor.fetchone()
    total_waiting = waiting_data["total_waiting"] if waiting_data else 0

    predicted_delay = total_waiting * avg_time

    bottleneck = False
    recommendation = None

    if utilization > 85 or total_waiting > 10:
        bottleneck = True
        recommendation = (
            f"⚠ Estimated delay: {round(predicted_delay, 2)} minutes. "
            f"Consider shifting LOW priority patients or adding staff."
        )
        # 🔥 AUTO OPTIMIZE WHEN OVERLOADED
        auto_reassign_patients(department)
    # 🔥 Fetch recent reassignment logs
    cursor.execute("""
        SELECT * FROM reassignment_logs
        WHERE department=%s
        ORDER BY created_at DESC
        LIMIT 5
    """, (department,))

    logs = cursor.fetchall()


    cursor.close()
    conn.close()

    fairness_index = calculate_fairness(department)
    optimization_score = calculate_optimization_score(department)
    # 🔥 Determine System Status (Step 1A)
    total_assigned = len(regular_patients) + len(emergency_patients)

    if total_assigned > 10:
        system_status = "Overloaded"
    elif total_assigned > 5:
        system_status = "Moderate Load"
    else:
        system_status = "Stable"

    


    return render_template(
    "doctor_dashboard.jinja",
    doctor_name=session.get("doctor_name"),
    department=department,
    regular_patients=regular_patients,
    emergency_patients=emergency_patients,
    avg_time=round(avg_time, 2),
    utilization=round(utilization, 2),
    bottleneck=bottleneck,
    recommendation=recommendation,
    logs=logs,
    fairness_index=fairness_index,
    optimization_score=optimization_score,
    system_status=system_status
)

# chart_data route for AJAX calls

@app.route("/chart_data")
def chart_data():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT department, COUNT(*) as total
        FROM patients
        WHERE status='waiting'
        GROUP BY department
    """)

    data = cursor.fetchall()

    cursor.close()
    conn.close()

    departments = [row["department"] for row in data]
    counts = [row["total"] for row in data]

    return {
        "departments": departments,
        "counts": counts
    }



# complete
@app.route("/complete/<int:patient_id>")
def complete_patient(patient_id):

    if "doctor_id" not in session:
        return redirect("/doctor_login")

    import random
    consultation_time = random.randint(5, 25)

    conn = get_db()
    cursor = conn.cursor()

    # Update patient
    cursor.execute("""
        UPDATE patients
        SET status='completed',
            consultation_duration=%s
        WHERE id=%s
    """, (consultation_time, patient_id))

    # 🔥 Update doctor workload stats
    cursor.execute("""
        UPDATE doctors
        SET total_consultation_time = total_consultation_time + %s,
            patients_completed = patients_completed + 1
        WHERE id = %s
    """, (consultation_time, session["doctor_id"]))

    conn.commit()

    # 🔥 REAL-TIME RE-OPTIMIZATION
    auto_reassign_patients(session["department"])

    cursor.close()
    conn.close()

    return redirect("/doctor_dashboard")



# ========================
# Patient Register
# ========================
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        aadhaar = request.form["aadhaar"]
        gender = request.form["gender"]
        dob = request.form["dob"]
        disease = request.form["disease"]

        birth_date = datetime.strptime(dob, "%Y-%m-%d")
        today = datetime.today()
        age = today.year - birth_date.year - (
            (today.month, today.day) < (birth_date.month, birth_date.day)
        )

        phone = request.form["phone"]
        whatsapp = request.form["whatsapp"]
        blood_group = request.form["blood_group"]
        address = request.form["address"]
        department = request.form["department"]

        oxygen = float(request.form["oxygen"])
        bp = float(request.form["bp"])
        temperature = float(request.form["temperature"])

        priority = calculate_priority(age, oxygen, temperature, bp, disease)
        status = "emergency" if priority == "HIGH" else "waiting"

        # ========================
        # ML Prediction + Explainability
        # ========================

        predicted_time, duration_explanation = predict_duration(
        age, oxygen, bp, temperature,
        department, priority, disease
        )

        no_show_prob, no_show_explanation = predict_no_show(
        age,
        priority,
        department,
        predicted_time
        )


        conn = get_db()
        cursor = conn.cursor()

        # ========================
        # SMART SHIFT-BASED LOAD BALANCING
        # ========================

        current_time = datetime.now().strftime("%H:%M:%S")

        cursor.execute("""
        SELECT d.id, d.name,
            COUNT(p.id) AS active_count
        FROM doctors d
        LEFT JOIN patients p
            ON d.id = p.doctor_id
            AND p.status IN ('waiting','emergency')
        WHERE d.department = %s
        AND d.is_active = 1
        GROUP BY d.id
        ORDER BY active_count ASC
        """, (department,))


        doctors = cursor.fetchall()

        selected_doctor = None
        lowest_load = float('inf')

        for doc in doctors:
            active = doc[2] or 0
            if active < lowest_load:
                lowest_load = active
                selected_doctor = doc

        if selected_doctor:
            doctor_id = selected_doctor[0]
            doctor_name = selected_doctor[1]
            explanation = (
                f"Assigned to Dr. {doctor_name} "
                f"(Active Shift | Lowest Load: {lowest_load} patients)."
            )
        else:
            doctor_id = None
            doctor_name = "Not Assigned"
            explanation = "No active doctor available in this department at this time."

        # ========================
        # INSERT PATIENT
        # ========================
        cursor.execute("""
        INSERT INTO patients
        (name, age, aadhaar, gender, dob, phone, whatsapp,
        blood_group, address, department,
        disease, priority, status, oxygen, bp, temperature,
        doctor_id, consultation_duration, no_show_probability,
        duration_explanation, no_show_explanation)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            name, age, aadhaar, gender, dob, phone, whatsapp,
            blood_group, address, department,
            disease, priority, status, oxygen, bp, temperature,
            doctor_id, predicted_time, no_show_prob,
            str(duration_explanation),
            str(no_show_explanation)
        ))


        conn.commit()
        patient_id = cursor.lastrowid

        # ========================
        # QUEUE POSITION
        # ========================
        cursor.execute("""
            SELECT COUNT(*) FROM patients
            WHERE department=%s
            AND status='waiting'
            AND id <= %s
        """, (department, patient_id))

        queue_number = cursor.fetchone()[0]
        estimated_wait = (queue_number - 1) * predicted_time


        cursor.close()
        conn.close()

        return render_template(
            "token.html",
            patient_id=patient_id,
            doctor_name=doctor_name,
            department=department,
            queue_number=queue_number,
            estimated_wait=round(estimated_wait, 2),
            explanation=explanation,
            priority=priority,
            duration_explanation=duration_explanation,
            no_show_explanation=no_show_explanation
        )

    return render_template("register.html")




# ========================
# Mark Emergency
# ========================
@app.route("/emergency/<int:patient_id>")
def emergency_patient(patient_id):
    if "doctor_id" not in session:
        return redirect("/")

    conn = get_db()
    cursor = conn.cursor()

    # Update to emergency
    cursor.execute("""
        UPDATE patients
        SET status = 'emergency',
            priority = 'HIGH'
        WHERE id = %s
    """, (patient_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect("/doctor_dashboard")



# ========================
# Live Status Page
# ========================
@app.route("/status/<int:patient_id>")
def live_status(patient_id):

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM patients WHERE id=%s", (patient_id,))
    patient = cursor.fetchone()

    if not patient:
        return "Patient not found"

    cursor.execute("""
        SELECT COUNT(*) as queue_position
        FROM patients
        WHERE department=%s
        AND status='waiting'
        AND id<=%s
    """, (patient['department'], patient_id))

    queue = cursor.fetchone()["queue_position"]

    cursor.close()
    conn.close()

    predicted_time,_ = predict_duration(
    patient["age"],
    patient["oxygen"],
    patient["bp"],
    patient["temperature"],
    patient["department"],
    patient["priority"],
    patient["disease"]
)

    estimated_wait = queue * predicted_time


    return render_template(
        "status.html",
        patient=patient,
        queue=queue,
        wait=estimated_wait
    )

# ========================
# Download Token PDF
# ========================
@app.route("/download/<int:patient_id>")
def download_token(patient_id):

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM patients WHERE id=%s", (patient_id,))
    patient = cursor.fetchone()

    cursor.close()
    conn.close()

    if not patient:
        return "Patient not found"

    # Ensure static folder exists
    if not os.path.exists("static"):
        os.makedirs("static")

    filename = f"token_{patient_id}.pdf"
    filepath = os.path.join("static", filename)

    doc = SimpleDocTemplate(filepath, pagesize=A4)
    elements = []

    styles = getSampleStyleSheet()

    elements.append(Paragraph("<b>Hospital Smart Queue System</b>", styles['Title']))
    elements.append(Spacer(1, 0.5 * inch))

    data = [
        ["Token ID:", patient["id"]],
        ["Name:", patient["name"]],
        ["Department:", patient["department"]],
        ["Priority:", patient["priority"]],
        ["Status:", patient["status"]]
    ]

    table = Table(data, colWidths=[150, 250])
    elements.append(table)

    doc.build(elements)

    return send_file(filepath, as_attachment=True)

@app.route("/simulate")
def simulate():

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM patients WHERE status='waiting'")
    waiting = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM doctors")
    doctors = cursor.fetchone()[0]

    avg_consult_time = 15

    current_delay = (waiting * avg_consult_time) / doctors if doctors > 0 else 0
    new_delay = (waiting * avg_consult_time) / (doctors + 1)

    cursor.close()
    conn.close()

    return f"""
    Current Estimated Delay: {round(current_delay,2)} minutes<br>
    If 1 more doctor added → Delay becomes: {round(new_delay,2)} minutes
    """




# ========================
# Run App
# ========================
if __name__ == "__main__":
    app.run(debug=True)
