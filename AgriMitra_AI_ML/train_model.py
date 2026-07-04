import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
import joblib

# =========================
# LOAD DATA
# =========================
df = pd.read_csv("augmented_soil_data.csv")

X = df[['Temperature', 'Humidity', 'Moisture']]
y = df['Status']

# =========================
# SPLIT DATA
# =========================
X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

# =========================
# MODEL TRAINING
# =========================
model = RandomForestClassifier(
    n_estimators=100,
    random_state=42
)

model.fit(X_train, y_train)

# =========================
# PREDICTION
# =========================
y_pred = model.predict(X_test)

# =========================
# EVALUATION
# =========================
acc = accuracy_score(y_test, y_pred)

print("\n===== RESULTS =====")
print("Accuracy:", acc)
print("\nClassification Report:\n", classification_report(y_test, y_pred))

# =========================
# SAVE MODEL
# =========================
joblib.dump(model, "soil_model.pkl")

print("\nModel saved as soil_model.pkl")