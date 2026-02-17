import pandas as pd
import numpy as np
import random
import joblib

from sklearn.preprocessing import LabelEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# ===============================
# 1️⃣ Generate Synthetic Data
# ===============================

num_samples = 2000

departments = ["Cardiology", "Orthopedics", "Neurology", "General"]
priorities = ["LOW", "MEDIUM", "HIGH"]

data = []

for _ in range(num_samples):
    age = random.randint(1, 85)
    department = random.choice(departments)
    priority = random.choice(priorities)
    predicted_duration = random.uniform(5, 40)

    # Realistic no-show logic
    no_show_prob = 0.1

    if priority == "LOW":
        no_show_prob += 0.2
    if age < 25:
        no_show_prob += 0.15
    if department == "General":
        no_show_prob += 0.1

    no_show = 1 if random.random() < no_show_prob else 0

    data.append([age, department, priority, predicted_duration, no_show])

df = pd.DataFrame(data, columns=[
    "age",
    "department",
    "priority",
    "predicted_duration",
    "no_show"
])

# ===============================
# 2️⃣ Encoding
# ===============================

le_dept = LabelEncoder()
le_priority = LabelEncoder()

df["department"] = le_dept.fit_transform(df["department"])
df["priority"] = le_priority.fit_transform(df["priority"])

# ===============================
# 3️⃣ Train Model
# ===============================

X = df[["age", "department", "priority", "predicted_duration"]]
y = df["no_show"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

model = LogisticRegression()
model.fit(X_train, y_train)

preds = model.predict(X_test)
print("Model Accuracy:", accuracy_score(y_test, preds))

# ===============================
# 4️⃣ Save Model
# ===============================

joblib.dump(model, "no_show_model.pkl")
joblib.dump(le_dept, "no_show_dept_encoder.pkl")
joblib.dump(le_priority, "no_show_priority_encoder.pkl")

print("No-Show model saved successfully!")
