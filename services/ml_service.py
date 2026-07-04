from datetime import datetime
from firebase_admin import firestore
from routes.firebase import firestore_db


def save_prediction_if_changed(
    uid,
    name,
    temperature,
    humidity,
    moisture,
    prediction,
    status,
    pump
):
    """
    Save prediction only if values changed.
    """

    # Get all prediction docs
    docs = firestore_db.collection("predictions").stream()

    last = None

    for doc in docs:

        data = doc.to_dict()

        if data.get("uid") == uid:
            last = data

    # Compare with latest found record
    if last:

        temp_same = abs(last.get("temperature", 0) - temperature) < 0.2
        hum_same = abs(last.get("humidity", 0) - humidity) < 1
        soil_same = abs(last.get("moisture", 0) - moisture) < 20
        pred_same = last.get("prediction") == prediction

        if temp_same and hum_same and soil_same and pred_same:
            return False

    # Save new prediction
    firestore_db.collection("predictions").add({

        "uid": uid,
        "name": name,

        "temperature": temperature,
        "humidity": humidity,
        "moisture": moisture,

        "prediction": prediction,

        "status": status,
        "pump": pump,

        "created_at": datetime.utcnow()

    })

    return True