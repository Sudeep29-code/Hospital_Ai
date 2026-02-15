from flask import Flask, render_template, request, redirect, session, send_file, url_for
import mysql.connector
import os
from datetime import datetime

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




# DOCTOR DASHBOARD
@app.route("/doctor_dashboard")
def doctor_dashboard():

    if "doctor_id" not in session:
        return redirect("/doctor_login")

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # 🔹 Regular Patients
    cursor.execute("""
        SELECT id, name, priority
        FROM patients
        WHERE department=%s
        AND status='waiting'
        AND priority='NORMAL'
        ORDER BY id ASC
    """, (session["department"],))

    regular_patients = cursor.fetchall()

    # 🔹 Emergency Patients
    cursor.execute("""
    SELECT * FROM patients
    WHERE department = %s
    AND status IN ('waiting','emergency')
    ORDER BY
        CASE
            WHEN priority = 'HIGH' THEN 1
            WHEN priority = 'MEDIUM' THEN 2
            ELSE 3
        END
""", (session["department"],))


    emergency_patients = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "doctor_dashboard.html",
        doctor_name=session["doctor_name"],
        department=session["department"],
        regular_patients=regular_patients,
        emergency_patients=emergency_patients
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

    cursor.execute("""
        UPDATE patients
        SET status='completed',
            consultation_duration=%s
        WHERE id=%s
    """, (consultation_time, patient_id))

    conn.commit()

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

        # Calculate Age
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

        # Priority using your function
        priority = calculate_priority(age, oxygen, temperature, bp, disease)
        status = "emergency" if priority == "HIGH" else "waiting"

        conn = get_db()
        cursor = conn.cursor()

        # ✅ FIXED INSERT (disease added correctly)
        cursor.execute("""
            INSERT INTO patients
            (name, age, aadhaar, gender, dob, phone, whatsapp,
             blood_group, address, department,
             disease, priority, status, oxygen, bp, temperature)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            name, age, aadhaar, gender, dob, phone, whatsapp,
            blood_group, address, department,
            disease, priority, status, oxygen, bp, temperature
        ))

        conn.commit()
        patient_id = cursor.lastrowid

        # Queue Position
        cursor.execute("""
            SELECT COUNT(*) FROM patients
            WHERE department=%s
            AND status='waiting'
            AND id <= %s
        """, (department, patient_id))

        queue_number = cursor.fetchone()[0]

        # AI Prediction
        predicted_time = predict_duration(
            age, oxygen, bp, temperature,
            department, priority, disease
        )

        estimated_wait = queue_number * predicted_time

        # Assign Doctor
        cursor.execute("""
            SELECT name FROM doctors
            WHERE department=%s
            LIMIT 1
        """, (department,))

        doctor_data = cursor.fetchone()
        doctor_name = doctor_data[0] if doctor_data else "Not Assigned"

        cursor.close()
        conn.close()

        return render_template(
            "token.html",
            patient_id=patient_id,
            doctor_name=doctor_name,
            department=department,
            queue_number=queue_number,
            estimated_wait=round(estimated_wait, 2),
            priority=priority
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

    estimated_wait = queue * 3

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





# ========================
# Run App
# ========================
if __name__ == "__main__":
    app.run(debug=True)
