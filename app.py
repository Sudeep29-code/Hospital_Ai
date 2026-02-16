from flask import Flask, render_template, request, redirect, session, send_file, url_for
import mysql.connector
import os
import random
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

import joblib
import numpy as np


# ReportLab Imports
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4





app = Flask(__name__)
app.secret_key = "supersecretkey123"

# ========================
# Load AI Model
# ========================
model = joblib.load("duration_model.pkl")
le_dept = joblib.load("dept_encoder.pkl")
le_priority = joblib.load("priority_encoder.pkl")
le_disease = joblib.load("disease_encoder.pkl")
no_show_model = None





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
# AI Duration Prediction
# ========================
def predict_duration(age, oxygen, bp, temperature, department, priority, disease):

    # Safe encoding for department
    if department in le_dept.classes_:
        dept_encoded = le_dept.transform([department])[0]
    else:
        dept_encoded = 0

    # Safe encoding for priority
    if priority in le_priority.classes_:
        priority_encoded = le_priority.transform([priority])[0]
    else:
        priority_encoded = 0

    # Safe encoding for disease
    disease = disease.lower()
    if disease in le_disease.classes_:
        disease_encoded = le_disease.transform([disease])[0]
    else:
        disease_encoded = 0

    features = np.array([[age, oxygen, bp, temperature,
                          dept_encoded, priority_encoded, disease_encoded]])

    prediction = model.predict(features)[0]

    return round(float(prediction), 2)



def predict_no_show(age, priority, department):
    return 0.15   # fixed 15% probability




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
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name, department
            FROM doctors
            WHERE doctor_id=%s AND password=%s
        """, (doctor_id, password))

        doctor = cursor.fetchone()

        cursor.close()
        conn.close()

        if doctor:
            session["doctor_id"] = doctor[0]
            session["doctor_name"] = doctor[1]
            session["department"] = doctor[2]   # 🔥 IMPORTANT
            return redirect("/doctor_dashboard")
        else:
            return "Invalid ID or Password"

    return render_template("doctor_login.html")


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
        predicted = predict_duration(
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

    # Normalize wait (assuming 0–60 mins)
    wait_score = max(0, 100 - avg_wait)

    # 🔥 Multi-objective weighted optimization
    final_score = 0.6 * fairness_score + 0.4 * wait_score

    return round(final_score, 2)

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
        auto_reassign_patients(dept[0])

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
        SELECT * FROM patients
        WHERE doctor_id = %s
        AND status IN ('waiting', 'emergency')
        ORDER BY
            CASE
                WHEN priority = 'HIGH' THEN 1
                WHEN priority = 'MEDIUM' THEN 2
                ELSE 3
            END,
            id ASC
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


    return render_template(
    "doctor_dashboard.html",
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
    optimization_score=optimization_score
)



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
        no_show_prob = predict_no_show(age, priority, department)


        conn = get_db()
        cursor = conn.cursor()

        # ------------------------------
        # 🔥 DOCTOR LOAD BALANCING
        # ------------------------------
        cursor.execute("""
            SELECT id, name, total_consultation_time, patients_completed
            FROM doctors
            WHERE department=%s
        """, (department,))

        doctors = cursor.fetchall()

        selected_doctor = None
        lowest_load = float('inf')

        for doc in doctors:
            completed = doc[3] or 0
            total_time = doc[2] or 0

            avg = total_time / completed if completed > 0 else 0

            if avg < lowest_load:
                lowest_load = avg
                selected_doctor = doc

        if selected_doctor:
            doctor_id = selected_doctor[0]
            doctor_name = selected_doctor[1]
        else:
            doctor_id = None
            doctor_name = "Not Assigned"
        # 🔥 Explainable AI Decision
        if selected_doctor:
            explanation = f"Assigned to Dr. {doctor_name} due to lowest workload (avg {round(lowest_load,2)} mins per patient)."
        else:
            explanation = "No doctor available in this department."

        # ------------------------------
        # INSERT PATIENT (NOW CORRECT)
        # ------------------------------
        cursor.execute("""
        INSERT INTO patients
        (name, age, aadhaar, gender, dob, phone, whatsapp,
        blood_group, address, department,
        disease, priority, status, oxygen, bp, temperature,
        doctor_id, no_show_probability)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
        name, age, aadhaar, gender, dob, phone, whatsapp,
        blood_group, address, department,
        disease, priority, status, oxygen, bp, temperature,
        doctor_id, no_show_prob
        ))


        conn.commit()
        patient_id = cursor.lastrowid
        # 🔥 Trigger dynamic re-optimization
        auto_reassign_patients(department)


        # ------------------------------
        # Queue Position
        # ------------------------------
        cursor.execute("""
            SELECT COUNT(*) FROM patients
            WHERE department=%s
            AND status='waiting'
            AND id <= %s
        """, (department, patient_id))

        queue_number = cursor.fetchone()[0]

        # ------------------------------
        # AI Prediction
        # ------------------------------
        predicted_time = predict_duration(
            age, oxygen, bp, temperature,
            department, priority, disease
        )

        estimated_wait = queue_number * predicted_time

        cursor.close()
        conn.close()

        return render_template(
            "token.html",
            patient_id=patient_id,
            doctor_name=doctor_name,
            department=department,
            queue_number=queue_number,
            estimated_wait=round(estimated_wait, 2),
            priority=priority,
            explanation=explanation  
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

    predicted_time = predict_duration(
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
