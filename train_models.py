import mysql.connector
import pandas as pd
import numpy as np
import joblib
import os

from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

# ==========================
# Connect to MySQL
# ==========================

try:
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="sudeep@29",
        database="hospital_db"
    )
except Exception as e:
    print("❌ Database connection failed:", e)
    exit()

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

if len(data) < 10:
    print("❌ Not enough completed cases to train model.")
    exit()

print(f"✅ Training on {len(data)} completed consultations")

# ==========================
# Clean Missing Values
# ==========================

data = data.dropna()

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
# Train/Test Split (Important for Hackathon)
# ==========================

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# ==========================
# Train Model
# ==========================

model = RandomForestRegressor(n_estimators=300, random_state=42)
model.fit(X_train, y_train)

# ==========================
# Evaluate Model
# ==========================

predictions = model.predict(X_test)
mae = mean_absolute_error(y_test, predictions)

print("✅ Model trained successfully!")
print("📊 Mean Absolute Error:", round(mae, 2), "minutes")

# ==========================
# Save Model & Encoders
# ==========================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

joblib.dump(model, os.path.join(BASE_DIR, "duration_model.pkl"))
joblib.dump(le_dept, os.path.join(BASE_DIR, "dept_encoder.pkl"))
joblib.dump(le_priority, os.path.join(BASE_DIR, "priority_encoder.pkl"))
joblib.dump(le_disease, os.path.join(BASE_DIR, "disease_encoder.pkl"))

print("✅ Model and encoders saved successfully in project folder!")
