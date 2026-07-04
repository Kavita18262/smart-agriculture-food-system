import firebase_admin
from firebase_admin import credentials, firestore, db

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