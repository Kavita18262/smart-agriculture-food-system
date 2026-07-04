import firebase_admin
from firebase_admin import credentials, firestore, db
import requests

# Initialize Firebase only once
if not firebase_admin._apps:

    cred = credentials.Certificate("firebase_key.json")

    firebase_admin.initialize_app(cred, {
        "databaseURL": "https://smart-farming-8c644-default-rtdb.asia-southeast1.firebasedatabase.app"
    })

# Firestore Database
firestore_db = firestore.client()

# Realtime Database
realtime_db = db.reference("/")
# ==========================
# Realtime Sensor Data
# ==========================

def get_sensor_data():

    sensor = realtime_db.child("sensorData").get()

    if not sensor:
        return {
            "temperature": 0,
            "humidity": 0,
            "soilMoisture": 0,
            "status": "Unknown",
            "pump": False
        }

    return {

        "temperature": sensor.get("temperature", 0),

        "humidity": sensor.get("humidity", 0),

        "soilMoisture": sensor.get("soilMoisture", 0),

        "status": sensor.get("status", "Unknown"),

        "pump": sensor.get("pump", False)

    }