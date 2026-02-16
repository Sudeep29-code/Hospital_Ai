import mysql.connector
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
import joblib

# ==========================
# Connect to MySQL
# ==========================

conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="kaibalya123",
    database="hospital_db"
)

query = """
SELECT age, oxygen, bp, temperature, department, priority, disease, consultation_duration
FROM patients
WHERE consultation_duration IS NOT NULL
"""

cursor = conn.cursor()
cursor.execute(query)

rows = cursor.fetchall()
columns = [desc[0] for desc in cursor.description]

data = pd.DataFrame(rows, columns=columns)

cursor.close()
conn.close()

# ==========================
# Check Data Availability
# ==========================

if len(data) < 5:
    print("Not enough completed cases to train model.")
    exit()

# ==========================
# Encode Categorical Features
# ==========================

le_dept = LabelEncoder()
le_priority = LabelEncoder()
le_disease = LabelEncoder()

data["department"] = le_dept.fit_transform(data["department"])
data["priority"] = le_priority.fit_transform(data["priority"])
data["disease"] = le_disease.fit_transform(data["disease"])

# ==========================
# Prepare Training Data
# ==========================

X = data[["age", "oxygen", "bp", "temperature",
          "department", "priority", "disease"]]

y = data["consultation_duration"]

# ==========================
# Train Model
# ==========================

model = RandomForestRegressor(n_estimators=200, random_state=42)
model.fit(X, y)

# ==========================
# Save Model & Encoders
# ==========================

joblib.dump(model, "duration_model.pkl")
joblib.dump(le_dept, "dept_encoder.pkl")
joblib.dump(le_priority, "priority_encoder.pkl")
joblib.dump(le_disease, "disease_encoder.pkl")

print("✅ Duration AI Model trained successfully on real hospital data!")
