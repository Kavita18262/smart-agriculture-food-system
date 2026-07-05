from flask import Flask, render_template, request, redirect, flash, session, jsonify, send_file, make_response
import os
from flask import send_file
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
from firebase_admin import auth
from dotenv import load_dotenv 
import subprocess 
import shutil 
import requests 
import re 
from datetime import datetime 
import io 
from services.ml_service import save_prediction_if_changed
from openai import OpenAI
from firebase import firestore_db
from firebase_admin import credentials, firestore, db,auth
from routes.auth import auth_bp
import pandas as pd
import joblib
from data.agritech_tools import AGRITECH_TOOLS
from datetime import timedelta
from routes.firebase import get_sensor_data
import cloudinary
import cloudinary.uploader
import cloudinary.api
from werkzeug.utils import secure_filename
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

df = pd.read_csv(os.path.join(BASE_DIR, "augmented_soil_data.csv"))

model = joblib.load(os.path.join(BASE_DIR, "soil_model.pkl"))

df.columns = (
    df.columns
    .str.strip()
    .str.replace("  ", "")   # removes double spaces if any
)

app = Flask(__name__)
app.register_blueprint(auth_bp)

@app.context_processor
def inject_user():

    photo = ""

    if "uid" in session:

        try:

            doc = firestore_db.collection("farmers").document(
                session["uid"]
            ).get()

            if doc.exists:

                photo = doc.to_dict().get("photo", "")

        except Exception as e:

            print("Photo Error:", e)

    return {

        "name": session.get("fullname", "Farmer"),

        "photo": photo

    }
@app.context_processor
def inject_translator():

    def tr(text):

        lang = session.get("lang", "en")

        return translate_text(text, lang)

    return {

        "tr": tr

    }


# Map language codes to display names for model instructions
LANG_MAP = {
    'en': 'English',
    'hi': 'Hindi',
    'pa': 'Punjabi',
    'gu': 'Gujarati',
    'mr': 'Marathi',
    'ta': 'Tamil'
}

load_dotenv(override=True)
app.secret_key = os.getenv(
    "SECRET_KEY",
    "AgriMitra_AI_2026_Smart_Farming_Project_Secret_Key"
)
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY:
    print("OPENAI_API_KEY loaded: True")
    client = OpenAI(api_key=OPENAI_API_KEY)
else:
    print("OPENAI_API_KEY loaded: False")
    client = None

NEWS_API_KEY = os.getenv("NEWS_API_KEY","1d4ed6258ac5461ab703fce0d5e8ed97")
VOICE_API_KEY = os.getenv("VOICE_API_KEY","sk_1b88c0dce6769244d708eaa04f422c57a8767f460ac04149")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "c35dd2607063f82a9a8f23b66aa7d7f7")
CITY = "Pune"


def build_fallback_answer(question: str) -> str:
    q = (question or "").lower()

    if any(term in q for term in ["black soil", "black cotton soil", "regur soil"]):
        return (
            "Black soil is well suited for crops like cotton, soybean, sorghum, pigeon pea, gram, sunflower, and maize. "
            "It retains moisture well and is very useful for crops that prefer clayey, fertile soil."
        )

    if any(term in q for term in ["alluvial soil", "red soil", "laterite soil", "desert soil", "mountain soil", "sandy soil", "clay soil", "loamy soil"]):
        return (
            f"For {question.strip() or 'that soil type'}, common crops are chosen based on the soil's water-holding capacity and fertility. "
            "For example, alluvial soil suits wheat and rice, red soil suits millets and pulses, and clayey soils are good for cotton and soybean."
        )

    if any(term in q for term in ["soil type", "soil quality", "soil fertility", "good soil", "soil suitable"]):
        return (
            "Soil suitability depends on texture, drainage, organic matter, and moisture holding capacity. "
            "Loamy soil is often the most versatile, while black soil is excellent for cotton and pulses, and sandy soil is better for crops that need fast drainage."
        )

    if any(word in q for word in ["yellow", "yellowing", "leaf", "leaves"]):
        return (
            "Yellowing leaves often mean nutrient stress, overwatering, or pest pressure. "
            "Check soil moisture, avoid waterlogging, and apply a balanced fertilizer if the crop looks weak."
        )

    if any(word in q for word in ["pest", "insect", "aphid", "worm", "bug"]):
        return (
            "Inspect the undersides of leaves and stems for insects or eggs. "
            "Remove affected leaves, improve airflow, and use neem oil or an approved pesticide if the infestation is serious."
        )

    if any(word in q for word in ["water", "watering", "irrigation"]):
        return (
            "Water early in the morning and avoid frequent shallow watering. "
            "Check soil moisture before irrigating so the roots get enough but not too much water."
        )

    if any(word in q for word in ["soil", "moisture", "fertilizer", "nutrient"]):
        return (
            "Use soil testing to guide fertilizer use. "
            "Apply nutrients based on crop stage and soil condition, and keep the soil evenly moist rather than waterlogged."
        )

    if any(word in q for word in ["tomato", "potato", "wheat", "rice", "maize", "cotton"]):
        return (
            f"For {question.strip() or 'your crop'}, monitor the plants closely for disease, moisture stress, and nutrient deficiency. "
            "Good spacing, proper irrigation, and regular field inspection usually make a big difference."
        )
    if any(word in q for word in ["dry", "wet", "moisture sensor", "soil moisture"]):
        return (

            "Your AgriMitra AI system predicts soil condition using the sensor and AI model. "

            "If the soil is Dry, irrigation is recommended. "

            "If the soil is Wet, do not irrigate until moisture decreases."

        )
    return (
        "A practical first step is to inspect the crop, soil moisture, and visible symptoms closely. "
        "If the issue is serious, contact a local agriculture extension officer with photos of the affected plants."
    )


def get_weather():
    url = f"https://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={WEATHER_API_KEY}&units=metric"

    response = requests.get(url)
    data = response.json()

    return {
        "temperature": data["main"]["temp"],
        "humidity": data["main"]["humidity"],
        "condition": data["weather"][0]["main"],
        "description": data["weather"][0]["description"],
        "wind": round(data["wind"]["speed"] * 3.6, 1),
        "icon": data["weather"][0]["icon"]
    }


def translate_text(text: str, target_lang: str) -> str:
    """Translate `text` to `target_lang` using Google's unofficial translate endpoint.
    Returns original text on failure or when target_lang is 'en' or empty."""
    if not text or not target_lang or target_lang == "en":
        return text
    try:
        params = {
            "client": "gtx",
            "sl": "auto",
            "tl": target_lang,
            "dt": "t",
            "q": text
        }
        resp = requests.get("https://translate.googleapis.com/translate_a/single", params=params, timeout=10)
        data = resp.json()
        # data[0] is list of translated segments
        translated = "".join([seg[0] for seg in data[0] if seg and len(seg) > 0 and seg[0]])
        return translated or text
    except Exception:
        return text




@app.route("/weather")
def weather_page():
    lang = session.get('lang', 'en')
    weather = get_weather()
    # translate weather description/condition if needed
    weather['description'] = translate_text(weather.get('description', ''), lang)
    weather['condition'] = translate_text(weather.get('condition', ''), lang)

    return render_template("weather.html", weather=weather)
@app.route("/api/weather")  
def api_weather():
    lang = session.get('lang', 'en')
    weather = get_weather()
    weather['description'] = translate_text(weather.get('description', ''), lang)
    weather['condition'] = translate_text(weather.get('condition', ''), lang)
    return weather
CROPS_DB = {
    "dry": ["Wheat", "Gram", "Bajra", "Millets", "Barley", "Groundnut"],
    "wet": ["Rice", "Sugarcane", "Jute", "Taro"],
    "hot": ["Cotton", "Maize", "Sorghum", "Sunflower"],
    "balanced": ["Tomato", "Onion", "Chilli", "Potato", "Vegetables", "Soybean"]
}

CROP_DETAILS = {
    "Wheat": {
        "soil_type": "Alluvial, loamy",
        "climate": "Cool, moderate rainfall",
        "season": "Rabi",
        "water_requirement": "4,000–5,000 m³/ha per season",
        "growth_habit": "Short-stature cereal crop with moderate irrigation needs.",
        "best_conditions": "Well-drained loamy soil, balanced fertilizer, and regular irrigation."
    },
    "Gram": {
        "soil_type": "Loamy, well-drained",
        "climate": "Cool, dry",
        "season": "Rabi",
        "water_requirement": "2,500–3,000 m³/ha per season",
        "growth_habit": "Pulse crop with low water needs and good nitrogen-fixing ability.",
        "best_conditions": "Sandy loam with good drainage and light irrigation."
    },
    "Bajra": {
        "soil_type": "Light, sandy loam",
        "climate": "Hot, low rainfall",
        "season": "Kharif",
        "water_requirement": "3,000–4,000 m³/ha per season",
        "growth_habit": "Drought-tolerant millet crop well suited to dry regions.",
        "best_conditions": "Warm climate, loose soil, and minimal irrigation."
    },
    "Millets": {
        "soil_type": "Red, sandy loam",
        "climate": "Warm, dry",
        "season": "Kharif/Rabi",
        "water_requirement": "2,500–3,500 m³/ha per season",
        "growth_habit": "Short-duration cereal crop that uses water efficiently.",
        "best_conditions": "Light soil, good drainage, and timely rain."
    },
    "Barley": {
        "soil_type": "Loamy, alkaline",
        "climate": "Cool, semi-arid",
        "season": "Rabi",
        "water_requirement": "3,500–4,500 m³/ha per season",
        "growth_habit": "Hardy cereal crop with moderate water use.",
        "best_conditions": "Fertile, well-drained soil and cooler weather."
    },
    "Groundnut": {
        "soil_type": "Sandy loam",
        "climate": "Warm, moderate rainfall",
        "season": "Kharif",
        "water_requirement": "4,000–5,000 m³/ha per season",
        "growth_habit": "Oilseed crop that needs steady moisture during pod formation.",
        "best_conditions": "Loose soil, warm weather, and light irrigation."
    },
    "Rice": {
        "soil_type": "Clayey, alluvial",
        "climate": "Warm, high rainfall",
        "season": "Kharif",
        "water_requirement": "10,000–12,000 m³/ha per season",
        "growth_habit": "Flooded paddy crop requiring continuous moisture.",
        "best_conditions": "Heavy soils with standing water and high humidity."
    },
    "Sugarcane": {
        "soil_type": "Loamy, clayey",
        "climate": "Tropical, humid",
        "season": "Long-duration",
        "water_requirement": "15,000–18,000 m³/ha per season",
        "growth_habit": "Tall tropical grass needing large water supply.",
        "best_conditions": "Deep fertile soil, warm climate, and good irrigation."
    },
    "Jute": {
        "soil_type": "Alluvial",
        "climate": "Humid, warm",
        "season": "Kharif",
        "water_requirement": "8,000–10,000 m³/ha per season",
        "growth_habit": "Fiber crop that grows quickly with regular moisture.",
        "best_conditions": "Moist, fertile soils and high humidity."
    },
    "Taro": {
        "soil_type": "Wet, clayey",
        "climate": "Humid, warm",
        "season": "Kharif",
        "water_requirement": "8,000–10,000 m³/ha per season",
        "growth_habit": "Tuber crop that needs wet conditions and shade.",
        "best_conditions": "Waterlogged soils and continuous moisture."
    },
    "Cotton": {
        "soil_type": "Black, deep loam",
        "climate": "Warm, dry",
        "season": "Kharif",
        "water_requirement": "6,000–7,000 m³/ha per season",
        "growth_habit": "Bushy fiber crop with moderate irrigation needs.",
        "best_conditions": "Deep soil, warm days, and dry picking weather."
    },
    "Maize": {
        "soil_type": "Loamy, well-drained",
        "climate": "Warm",
        "season": "Kharif/Rabi",
        "water_requirement": "5,000–6,500 m³/ha per season",
        "growth_habit": "Tall cereal crop with steady moisture demand.",
        "best_conditions": "Fertile soils and balanced irrigation."
    },
    "Sorghum": {
        "soil_type": "Red, loamy",
        "climate": "Warm, dry",
        "season": "Kharif",
        "water_requirement": "3,500–4,500 m³/ha per season",
        "growth_habit": "Drought-tolerant grain crop that can survive low rainfall.",
        "best_conditions": "Light soils and infrequent irrigation."
    },
    "Sunflower": {
        "soil_type": "Loamy, sandy",
        "climate": "Warm, dry",
        "season": "Rabi",
        "water_requirement": "4,000–5,000 m³/ha per season",
        "growth_habit": "Oilseed crop with moderate water use and high sunlight need.",
        "best_conditions": "Well-drained soil and full sun exposure."
    },
    "Tomato": {
        "soil_type": "Loamy, fertile",
        "climate": "Warm, moderate",
        "season": "Kharif/Rabi",
        "water_requirement": "6,000–7,500 m³/ha per season",
        "growth_habit": "Vegetable crop with frequent watering and staking needs.",
        "best_conditions": "Rich soil, regular irrigation, and good airflow."
    },
    "Onion": {
        "soil_type": "Loamy, sandy",
        "climate": "Cool, dry",
        "season": "Rabi",
        "water_requirement": "4,500–5,500 m³/ha per season",
        "growth_habit": "Bulb crop with steady moisture requirements.",
        "best_conditions": "Well-drained soil, low humidity, and light irrigation."
    },
    "Chilli": {
        "soil_type": "Loamy, fertile",
        "climate": "Warm",
        "season": "Kharif/Rabi",
        "water_requirement": "4,500–5,500 m³/ha per season",
        "growth_habit": "Spicy vegetable crop with moderate water needs.",
        "best_conditions": "Warm days, rich soil, and consistent moisture."
    },
    "Potato": {
        "soil_type": "Loamy, well-drained",
        "climate": "Cool",
        "season": "Rabi",
        "water_requirement": "5,000–6,000 m³/ha per season",
        "growth_habit": "Tuber crop needing regular watering and loose soil.",
        "best_conditions": "Cool climate, loose soil, and even moisture."
    },
    "Vegetables": {
        "soil_type": "Loamy, fertile",
        "climate": "Moderate",
        "season": "Year-round",
        "water_requirement": "5,000–7,000 m³/ha per season",
        "growth_habit": "Mixed vegetable crops with varying needs, usually regular irrigation.",
        "best_conditions": "Rich soil, regular watering, and pest control."
    },
    "Soybean": {
        "soil_type": "Loamy, well-drained",
        "climate": "Warm",
        "season": "Kharif",
        "water_requirement": "4,000–5,000 m³/ha per season",
        "growth_habit": "Legume crop that fixes nitrogen and needs moderate moisture.",
        "best_conditions": "Warm weather, balanced soil, and good drainage."
    }
}

@app.route("/crop")
def crop_page():
    return render_template("crop.html")
@app.route("/agritech-tools")
def agritech_tools():
    return render_template(
        "agritech_tools.html",
        categories=AGRITECH_TOOLS
    )
@app.route("/agritech-tools/<category>")
def show_category(category):
    data = AGRITECH_TOOLS.get(category, [])
    return render_template(
        "category_tools.html",
        category_name=category,
        tools=data
    )
@app.route("/analytics")
def analytics():

    data = firestore_db.collection("predictions").stream()
    records = [d.to_dict() for d in data]

    print("Total Prediction Records:", len(records))

    total = len(records)

    if total == 0:
        healthy_percent = 0
        avg_moisture = 0
        avg_temp = 0
    else:
        healthy_count = sum(1 for r in records if r.get("prediction") == "Healthy")

        healthy_percent = round((healthy_count / total) * 100, 2)

        avg_moisture = round(sum(r.get("moisture", 0) for r in records) / total, 2)

        avg_temp = round(sum(r.get("temperature", 0) for r in records) / total, 2)

    total_farmers = len(firestore_db.collection("farmers").get())
    sensor = get_sensor_data()
    insights = []

    if sensor["temperature"] > 35:
        insights.append("🔥 High temperature detected. Increase irrigation.")

    if sensor["humidity"] < 40:
        insights.append("💧 Humidity is low. Crop stress is possible.")

    if sensor["soilMoisture"] >= 3500:

        insights.append(
        "🌱 Soil is Dry. Irrigation Recommended."
    )

    elif sensor["soilMoisture"] <= 1000:

        insights.append(
        "💧 Soil Moisture is High."
        )

    if sensor["status"].lower() == "dry":
        insights.append("⚠️ Soil condition is Dry.")

    if sensor["pump"]:
        insights.append("🚰 Irrigation pump is currently ON.")
        
    else:
        insights.append("🚰 Irrigation pump is currently OFF.")

    if not insights:
        insights.append("✅ Farm conditions are currently normal.")
    return render_template(
    "analytics.html",
    total_farmers=total_farmers,
    healthy_percent=healthy_percent,
    avg_soil=avg_moisture,
    avg_temp=avg_temp,
    sensor=sensor,
    records=records,
    ai_insights=insights
)
@app.route("/debug-predictions")
def debug_predictions():
    data = firestore_db.collection("predictions").get()

    result = []
    for d in data:
        result.append(d.to_dict())

    return {"count": len(result), "data": result}
@app.route('/news')
def news():
    """Return recent agriculture news headlines, translated to user's language."""
    if not NEWS_API_KEY:
        return jsonify({'error': 'NEWS_API_KEY not configured'}), 400
    lang = session.get('lang', 'en')
    params = {
        'q': 'agriculture OR farming OR crops',
        'pageSize': 10,
        'language': 'en'
    }
    headers = {'Authorization': NEWS_API_KEY}
    try:
        resp = requests.get('https://newsapi.org/v2/everything', params=params, headers=headers, timeout=10)
        data = resp.json()
        articles = data.get('articles', [])[:10]
        out = []
        for a in articles:
            title = a.get('title') or ''
            desc = a.get('description') or ''
            translated_title = translate_text(title, lang)
            translated_desc = translate_text(desc, lang)
            out.append({
                'title': translated_title,
                'description': translated_desc,
                'url': a.get('url')
            })
        return jsonify({'articles': out})
    except Exception as e:
        print('News fetch failed:', e)
        return jsonify({'error': 'failed to fetch news'})



@app.route("/")
def splash():
    return render_template("splash.html")

@app.route("/language")
def language():
    return render_template("language.html")

@app.route("/home")
def home():
    return render_template("home.html")

from datetime import timedelta
from flask import request, session, redirect, render_template, flash

# IMPORTANT: put this near app initialization
app.secret_key = "AgriMitra_AI_2026_Smart_Farming_Project_Secret_Key"
app.permanent_session_lifetime = timedelta(days=7)

def firebase_sign_in(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={os.getenv('FIREBASE_API_KEY')}"

    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }

    response = requests.post(url, json=payload)

    if response.status_code == 200:
        return response.json()
    else:
        return None
@app.route("/login", methods=["GET", "POST"])
def login():

    print("========== LOGIN ROUTE CALLED ==========")

    if request.method == "POST":

        email = request.form.get("email").strip().lower()
        password = request.form.get("password")
        remember = request.form.get("remember") == "on"

        # Firebase Authentication
        user = firebase_sign_in(email, password)

        if not user:
            flash("Invalid email or password.")
            return redirect("/login")

        uid = user["localId"]

        print("LOGIN UID:", uid)

        # Firestore Document
        doc_ref = firestore_db.collection("farmers").document(uid)

        print("Document Path:", doc_ref.path)

        doc = doc_ref.get()
        print("Document Exists:", doc.exists)

        if doc.exists:
            print("Firestore Data:", doc.to_dict())
        else:
            print("NO DOCUMENT FOUND")

        print("Document Exists:", doc.exists)

        fullname = "Farmer"

        if doc.exists:

            data = doc.to_dict()

            print("Firestore Data:", data)

            fullname = data.get("fullname", "Farmer")

        print("Final Fullname:", fullname)

        # Save Session
        session.clear()

        session["uid"] = uid
        session["fullname"] = fullname
        session["email"] = email
        session["id_token"] = user["idToken"]
        session["user_id"] = uid
        session.permanent = remember

        print("Session Fullname Saved:", session.get("fullname"))
        print("Complete Session:", dict(session))

        flash("Login successful!")

        return redirect("/dashboard")

    return render_template("login.html")


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "POST":
        email = request.form["email"].strip()

        api_key = os.getenv("FIREBASE_API_KEY")

        url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={api_key}"

        payload = {
            "requestType": "PASSWORD_RESET",
            "email": email
        }

        response = requests.post(url, json=payload)

        if response.status_code == 200:
            flash("Password reset email sent! Check your inbox.")
            return redirect("/login")
        else:
            flash("Error: Email not found or invalid.")
            return redirect("/forgot-password")

    return render_template("forgot_password.html")
# Opens the AI Assistant page
# ==========================================
# CONVERSATION HELPER FUNCTIONS
# ==========================================

import uuid


def _ensure_conversations():

    if "conversations" not in session:

        session["conversations"] = {}

    if "active_conversation" not in session:

        cid = str(uuid.uuid4())

        session["active_conversation"] = cid

        session["conversations"][cid] = {

            "id": cid,

            "title": "New Chat",

            "history": []

        }

    session.modified = True


@app.route("/assistant")
def assistant():
    chat_history = session.get("chat_history", [])
    fullname = session.get('fullname', 'Farmer')
    return render_template("assistant.html", chat_history=chat_history, fullname=fullname)


@app.route('/set_language', methods=['POST'])
def set_language():
    lang = (request.form.get('lang') or request.json and request.json.get('lang'))
    if not lang:
        return jsonify({'error': 'No language provided'}), 400
    session['lang'] = lang
    return jsonify({'success': True, 'lang': lang})


def _ensure_conversations():
    """Ensure session has a conversations structure and active conversation id."""
    if 'conversations' not in session:
        session['conversations'] = {}
    if 'active_conversation' not in session:
        # create default conversation
        session['conversations']['default'] = {
            'id': 'default',
            'title': 'New Chat',
            'history': session.get('chat_history', [])
        }
        session['active_conversation'] = 'default'
    session.modified = True

@app.route('/conversations', methods=['GET'])
def list_conversations():
    _ensure_conversations()
    convs = []
    for c in session['conversations'].values():
        history = c.get('history', []) or []
        last = history[-1]['content'] if history else ''
        last_ts = history[-1].get('timestamp') if history else ''
        convs.append({'id': c['id'], 'title': c.get('title', 'Chat'), 'last': last, 'last_ts': last_ts})
    return jsonify({'conversations': convs, 'active': session.get('active_conversation')})


@app.route('/conversations', methods=['POST'])
def create_conversation():
    _ensure_conversations()
    import uuid
    cid = str(uuid.uuid4())
    title = request.form.get('title') or request.json and request.json.get('title') or 'New Chat'
    session['conversations'][cid] = {'id': cid, 'title': title, 'history': []}
    session['active_conversation'] = cid
    session['chat_history'] = []
    session.modified = True
    return jsonify({'id': cid, 'title': title})


@app.route('/conversations/<conv_id>', methods=['GET'])
def get_conversation(conv_id):
    _ensure_conversations()
    conv = session['conversations'].get(conv_id)
    if not conv:
        return jsonify({'error': 'not found'}), 404
    return jsonify({'id': conv_id, 'title': conv.get('title'), 'history': conv.get('history', [])})


@app.route('/conversations/<conv_id>/set_active', methods=['POST'])
def set_active_conversation(conv_id):
    _ensure_conversations()
    if conv_id not in session['conversations']:
        return jsonify({'error': 'not found'}), 404
    session['active_conversation'] = conv_id
    session['chat_history'] = session['conversations'][conv_id].get('history', [])
    return jsonify({'success': True, 'active': conv_id})


@app.route('/conversations/<conv_id>/clear', methods=['POST'])
def clear_conversation(conv_id):
    _ensure_conversations()
    conv = session['conversations'].get(conv_id)
    if not conv:
        return jsonify({'error': 'not found'}), 404
    conv['history'] = []
    if session.get('active_conversation') == conv_id:
        session['chat_history'] = []
    session['conversations'][conv_id] = conv
    return jsonify({'success': True})


@app.route('/conversations/<conv_id>/delete', methods=['POST'])
def delete_conversation(conv_id):
    _ensure_conversations()
    if conv_id not in session['conversations']:
        return jsonify({'error': 'not found'}), 404
    del session['conversations'][conv_id]
    # if deleted active, switch to default or first
    if session.get('active_conversation') == conv_id:
        keys = list(session['conversations'].keys())
        if keys:
            session['active_conversation'] = keys[0]
            session['chat_history'] = session['conversations'][session['active_conversation']]['history']
        else:
            session['active_conversation'] = None
            session['chat_history'] = []
    return jsonify({'success': True, 'active': session.get('active_conversation')})


@app.route('/set_name', methods=['POST'])
def set_name():
    name = (request.form.get('name') or (request.json and request.json.get('name')) or '').strip()
    if not name:
        return jsonify({'error': 'No name provided'}), 400
    session['fullname'] = name
    return jsonify({'success': True, 'fullname': name})

@app.route("/clear_chat",methods=["POST"])
def clear_chat():

    session["chat_history"]=[]

    _ensure_conversations()

    active=session.get("active_conversation")

    if active:

        session["conversations"][active]["history"]=[]

    session.modified=True

    return jsonify({

        "success":True

    })

@app.route("/ask_ai", methods=["POST"])
def ask_ai():

    question = (request.form.get("question") or "").strip()

    if not question:
        return jsonify({"error": "Please enter a farming question first."}), 400

    # load active conversation
    _ensure_conversations()
    active_conv = session.get('active_conversation', 'default')
    conv = session['conversations'].get(active_conv)
    chat_history = conv.get('history', []) if conv else session.get("chat_history", [])
    if not isinstance(chat_history, list):
        chat_history = []

    user_entry = {
        "role": "user",
        "content": question,
        "timestamp": datetime.utcnow().strftime("%H:%M")
    }
    chat_history.append(user_entry)
    messages = [
        {
            "role": "system",
            "content": (
                "You are AgriMitra AI, an expert agriculture assistant. "
                "Answer only farming-related questions. "
                "Give practical, short and easy-to-understand advice for farmers. "
                "Be friendly and conversational; keep tone warm and encouraging to farmers."
            )
        }
    ]
    messages.extend(chat_history[-12:])
    lang = session.get("lang", "en")
    # request mode: 'model' => ask model to reply in selected language; 'translate' => get English answer then translate
    mode = (request.form.get('mode') or (request.json and request.json.get('mode')) or 'model')
    prefer_model_language = True if mode != 'translate' else False
    # local hour (client) for contextual greeting
    local_hour = None
    try:
        lh = request.form.get('local_hour') or (request.json and request.json.get('local_hour'))
        if lh is not None:
            local_hour = int(lh)
    except Exception:
        local_hour = None

    # Try OpenAI first
    if client:
        try:
            messages_for_openai = list(messages)
            # If user prefers model-language mode, instruct OpenAI to reply in that language
            if prefer_model_language and lang and lang != 'en':
                lang_name = LANG_MAP.get(lang, lang)
                messages_for_openai.append({
                    "role": "system",
                    "content": f"Always reply in {lang_name}. Keep answers short, practical and farmer-friendly."
                })
            # If client provided local hour, ask model to begin with an appropriate greeting using the user's full name
            if local_hour is not None:
                fullname = session.get('fullname', 'Farmer')
                messages_for_openai.append({
                    "role": "system",
                    "content": (
                        f"Begin your reply with an appropriate short greeting for hour {local_hour}, "
                        f"addressed to {fullname} (for example: 'Good morning, {fullname}'). Then answer the question."
                    )
                })

            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=messages_for_openai,
                temperature=0.5
            )

            answer = response.choices[0].message.content
            # If mode is 'translate', translate OpenAI's output to user's language; otherwise assume model replied in desired language
            if prefer_model_language:
                final_answer = answer
            else:
                final_answer = translate_text(answer, lang) if lang != 'en' else answer

            chat_history.append({
                "role": "assistant",
                "content": final_answer,
                "timestamp": datetime.utcnow().strftime("%H:%M")
            })
            # save to active conv
            session['conversations'][active_conv]['history'] = chat_history
            session["chat_history"] = chat_history
            # ==========================================
# AUTO CONVERSATION TITLE
# ==========================================

            if session["conversations"][active_conv]["title"] == "New Chat":
                title = question.strip()

                if len(title) > 35:
                    title = title[:35] + "..."

                session["conversations"][active_conv]["title"] = title
            session.modified = True
            return jsonify({"answer": final_answer, "history": chat_history})

        except Exception as exc:
            print("OpenAI failed:", exc)

    # Fallback to local Ollama
    try:
        # Build a prompt for Ollama. Respect user's mode preference.
        base_instr = messages[0]["content"]
        ollama_prompt_parts = [base_instr]
        if prefer_model_language and lang and lang != 'en':
            lang_name = LANG_MAP.get(lang, lang)
            ollama_prompt_parts.append(f"Always reply in {lang_name}. Keep answers short, practical and farmer-friendly.")
        # If client provided local hour, ask Ollama to begin with a personalized greeting
        if local_hour is not None:
            fullname = session.get('fullname', 'Farmer')
            ollama_prompt_parts.append(
                f"Begin your reply with an appropriate short greeting for hour {local_hour}, addressed to {fullname} (for example: 'Good morning, {fullname}'). Then answer the question."
            )
        # Add the user question
        ollama_prompt_parts.append(f"Question: {question}")
        ollama_input = "\n\n".join(ollama_prompt_parts)

        ollama_command = ["ollama", "run", "llama3:latest", ollama_input]
        # Increase timeout and ensure utf-8 decoding; replace undecodable bytes
        ollama_proc = subprocess.run(
            ollama_command,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=120
        )

        if ollama_proc.returncode == 0:
            answer = (ollama_proc.stdout or "").strip()
            if answer:
                if prefer_model_language:
                    final_ans = answer
                else:
                    final_ans = translate_text(answer, lang) if lang != 'en' else answer

                chat_history.append({
                    "role": "assistant",
                    "content": final_ans,
                    "timestamp": datetime.utcnow().strftime("%H:%M")
                })
                session['conversations'][active_conv]['history'] = chat_history
                session["chat_history"] = chat_history
                if session["conversations"][active_conv]["title"] == "New Chat":
                    title = question.strip()
                    if len(title) > 35:
                        title = title[:35] + "..."
                    session["conversations"][active_conv]["title"] = title
                session.modified = True
                return jsonify({"answer": final_ans, "history": chat_history})
            else:
                print("Ollama returned no output.")
        else:
            stderr = (ollama_proc.stderr or "").strip()
            print("Ollama error:", stderr)
    except subprocess.TimeoutExpired as te:
        print("Ollama timeout:", te)
    except Exception as ollama_exc:
        print("Ollama execution failed:", ollama_exc)

    # Final fallback
    fallback_answer = build_fallback_answer(question)
    translated = translate_text(fallback_answer, lang)
    chat_history.append({
        "role": "assistant",
        "content": translated,
        "timestamp": datetime.utcnow().strftime("%H:%M")
    })
    session['conversations'][active_conv]['history'] = chat_history
    session["chat_history"] = chat_history
    if session["conversations"][active_conv]["title"] == "New Chat":
        title = question.strip()
        if len(title) > 35:
            title = title[:35] + "..."

        session["conversations"][active_conv]["title"] = title

    session.modified = True
    return jsonify({"answer": translated, "history": chat_history})


@app.route('/tts', methods=['POST'])
def tts():
    """Return TTS audio for provided `text`. Prefers `gTTS` fallback when no external voice API configured."""
    text = (request.form.get('text') or (request.json and request.json.get('text')) or '').strip()
    if not text:
        return jsonify({'error': 'No text provided'}), 400

    # Determine language for TTS. Map session lang to gTTS-supported codes where possible.
    lang = session.get('lang', 'en')
    supported = {'en': 'en', 'hi': 'hi', 'pa': 'pa', 'gu': 'gu', 'mr': 'mr', 'ta': 'ta'}
    tts_lang = supported.get(lang, 'en')

    # Try provider via VOICE_API_KEY (not implemented) — fallback to gTTS
    try:
        from gtts import gTTS
    except Exception as e:
        print('gTTS not available:', e)
        return jsonify({'error': 'gTTS not installed. Run `pip install gTTS` or configure a voice provider.'}), 500

    try:
        tts_obj = gTTS(text=text, lang=tts_lang)
        mp3_fp = io.BytesIO()
        tts_obj.write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        return send_file(mp3_fp, mimetype='audio/mpeg', as_attachment=False, download_name='tts.mp3')
    except Exception as e:
        print('TTS generation failed:', e)
        return jsonify({'error': 'TTS generation failed'}), 500

@app.route("/dashboard")
def dashboard():

    if "uid" not in session:
        return redirect("/login")

    uid = session["uid"]
    name = session.get("fullname", "Farmer")

    # ==========================================
    # SENSOR DATA
    # ==========================================

    sensor = get_sensor_data()

    latest_temp = sensor["temperature"]
    latest_humi = sensor["humidity"]
    latest_soil = sensor["soilMoisture"]

    labels = ["Current"]
    temp = [latest_temp]
    humi = [latest_humi]
    soil = [latest_soil]

    # ==========================================
    # AI MODEL PREDICTION
    # ==========================================

    prediction = model.predict(
        [[latest_temp, latest_humi, latest_soil]]
    )[0]

    status = str(prediction).capitalize()

    # ==========================================
    # AI RECOMMENDATION
    # ==========================================

    if status == "Dry":

        recommendation = {

            "title": "⚠ Soil is Dry",

            "badge": "Irrigation Required",

            "tips": [

                "💧 Turn ON irrigation pump immediately",

                "🌱 Water the crop to improve soil moisture",

                "☀ Avoid irrigation during afternoon",

                "📊 Check soil moisture after watering"

            ]

        }

    else:

        recommendation = {

            "title": "✅ Soil is Wet",

            "badge": "No Irrigation Needed",

            "tips": [

                "🌿 Soil moisture is sufficient",

                "🚫 Do not irrigate now",

                "📈 Continue monitoring sensor readings",

                "💚 Current moisture level is healthy"

            ]

        }

    


    # ==========================================
    # WEATHER
    # ==========================================

    weather = get_weather()

    # ==========================================
    # SAVE PREDICTION
    # ==========================================

    save_prediction_if_changed(

        uid=uid,

        name=name,

        temperature=latest_temp,

        humidity=latest_humi,

        moisture=latest_soil,

        prediction=status,

        status=sensor["status"],

        pump=sensor["pump"]

    )

    # ==========================================
    # FARM DETAILS
    # ==========================================

    farm = {}

    doc = firestore_db.collection("farmers").document(uid).get()

    if doc.exists:

        farm = doc.to_dict()

    farm.setdefault("crop_type", "")
    farm.setdefault("soil_type", "")
    farm.setdefault("farm_area", "")
    farm.setdefault("irrigation_type", "")
    farm.setdefault("location", "")

    # ==========================================
    # RENDER PAGE
    # ==========================================

    return render_template(

        "dashboard.html",

        name=name,

        labels=labels,

        temp=temp,

        humi=humi,

        soil=soil,

        prediction=status,

        recommendation=recommendation,

        latest_temp=latest_temp,

        latest_humi=latest_humi,

        latest_soil=latest_soil,

        weather=weather,

        farm=farm

    )
@app.route("/profile")
def profile():

    if "uid" not in session:
        flash("Please login first.")
        return redirect("/login")

    uid = session["uid"]
    name = session.get("fullname", "Farmer")

    # ==========================
    # User Data
    # ==========================

    user = {
        "uid": uid,
        "fullname": name,
        "email": session.get("email", ""),
        "mobile": "",
        "location": "",
        "language": "English",
        "crop_type": "",
        "soil_type": "",
        "farm_area": "",
        "irrigation_type": "",
        "photo": ""
    }

    try:

        doc = firestore_db.collection("farmers").document(uid).get()

        if doc.exists:

            data = doc.to_dict()

            user.update(data)

    except Exception as e:

        print("Firestore Error:", e)

    # ==========================
    # Sensor Data
    # ==========================

    sensor = get_sensor_data()

    latest_temp = sensor["temperature"]
    latest_humi = sensor["humidity"]
    latest_soil = sensor["soilMoisture"]

    # ==========================
    # Prediction
    # ==========================

    prediction = model.predict(
        [[latest_temp, latest_humi, latest_soil]]
    )[0]

    status = str(prediction).capitalize()

    # ==========================
    # Photo
    # ==========================

    photo = user.get("photo", "")

    return render_template(

        "profile.html",

        user=user,

        photo=photo,

        sensor=sensor,

        prediction=status

    )
@app.route("/edit-profile", methods=["GET", "POST"])
def edit_profile():

    if "uid" not in session:
        return redirect("/login")

    uid = session["uid"]
    doc_ref = firestore_db.collection("farmers").document(uid)

    # -----------------------------
    # SAVE PROFILE
    # -----------------------------
    if request.method == "POST":

        data = {

            "fullname": request.form.get("fullname", "").strip(),

            "mobile": request.form.get("mobile", "").strip(),

            "location": request.form.get("location", "").strip(),

            "language": request.form.get("language", "").strip(),

            "crop_type": request.form.get("crop_type", "").strip(),

            "soil_type": request.form.get("soil_type", "").strip(),

            "farm_area": request.form.get("farm_area", "").strip(),

            "irrigation_type": request.form.get("irrigation_type", "").strip(),

            "about": request.form.get("about", "").strip()

        }

        # Firestore Update
        doc_ref.set(data, merge=True)

        # Session Update
        session["fullname"] = data["fullname"]

        flash("✅ Profile updated successfully!", "success")

        return redirect("/profile")

    # -----------------------------
    # LOAD PROFILE
    # -----------------------------
    user = {}

    doc = doc_ref.get()

    if doc.exists:
        user = doc.to_dict()

    # Email session se lena
    user["email"] = session.get("email", "")

    return render_template(
        "edit_profile.html",
        user=user
    )
@app.route("/upload-profile-photo", methods=["POST"])
def upload_profile_photo():

    if "uid" not in session:
        return redirect("/login")

    uid = session["uid"]

    if "photo" not in request.files:

        flash("No file selected.")
        return redirect("/profile")

    file = request.files["photo"]

    if file.filename == "":

        flash("Please select an image.")
        return redirect("/profile")

    try:

        # Upload to Cloudinary
        result = cloudinary.uploader.upload(

            file,

            folder="AgriMitra/ProfilePhotos",

            public_id=uid,

            overwrite=True,

            resource_type="image"

        )

        photo_url = result["secure_url"]

        # Save URL to Firestore
        firestore_db.collection("farmers").document(uid).set(

            {

                "photo": photo_url

            },

            merge=True

        )

        flash("Profile photo updated successfully!")

    except Exception as e:

        print(e)

        flash("Image upload failed.")

    return redirect("/profile")
@app.route("/remove-profile-photo")
def remove_photo():

    if "uid" not in session:
        return redirect("/login")

    uid = session["uid"]

    try:

        firestore_db.collection("farmers").document(uid).update({

            "photo": ""

        })

        flash("Profile photo removed successfully.")

    except Exception as e:

        print("REMOVE PHOTO ERROR:", e)

        flash("Unable to remove photo.")

    return redirect("/profile")
def remove_profile_photo():

    if "uid" not in session:
        return redirect("/login")

    firestore_db.collection("farmers").document(session["uid"]).update({

        "photo": firestore.DELETE_FIELD

    })

    flash("Profile photo removed.")

    return redirect("/profile")
@app.route("/delete-account", methods=["POST"])
def delete_account():

    if "uid" not in session:
        return redirect("/login")

    uid = session["uid"]

    try:

        # Delete Firestore document
        firestore_db.collection("farmers").document(uid).delete()

        # Delete Firebase Authentication account
        auth.delete_user(uid)

        # Logout user
        session.clear()

        flash("Your account has been deleted successfully.")

        return redirect("/")

    except Exception as e:

        print("DELETE ACCOUNT ERROR:", e)

        flash("Unable to delete account.")

        return redirect("/profile")
@app.route("/save-farm", methods=["POST"])
def save_farm():

    if "uid" not in session:
        return redirect("/login")

    uid = session["uid"]

    # ==========================
    # CROP
    # ==========================

    crop_type = request.form.get("crop_type")

    if crop_type == "manual":
        crop_type = request.form.get("crop_manual", "").strip()

    # ==========================
    # SOIL
    # ==========================

    soil_type = request.form.get("soil_type")

    if soil_type == "manual":
        soil_type = request.form.get("soil_manual", "").strip()

    # ==========================
    # IRRIGATION
    # ==========================

    irrigation_type = request.form.get("irrigation_type")

    if irrigation_type == "manual":
        irrigation_type = request.form.get("irrigation_manual", "").strip()

    # ==========================
    # FARM AREA
    # ==========================

    farm_area = request.form.get("farm_area", "").strip()

    try:
        farm_area = float(farm_area)
    except:
        farm_area = 0.0

    # ==========================
    # SAVE TO FIRESTORE
    # ==========================

    firestore_db.collection("farmers").document(uid).set({

        "crop_type": crop_type,
        "soil_type": soil_type,
        "farm_area": farm_area,
        "irrigation_type": irrigation_type

    }, merge=True)

    flash("✅ Farm details saved successfully!", "success")

    return redirect("/dashboard")
@app.route("/logout")
def logout():

    session.clear()

    flash("Logged out successfully.")

    return redirect("/")
@app.route("/download-profile")
def download_profile():

    if "uid" not in session:
        return redirect("/login")

    uid = session["uid"]

    doc = firestore_db.collection("farmers").document(uid).get()

    if not doc.exists:
        flash("Profile not found.")
        return redirect("/profile")

    user = doc.to_dict()

    buffer = BytesIO()

    pdf = SimpleDocTemplate(buffer)

    styles = getSampleStyleSheet()

    story = []

    story.append(Paragraph("<b>AgriMitra AI - Farmer Profile</b>", styles["Title"]))

    story.append(Paragraph(
        f"Generated on: {datetime.now().strftime('%d-%m-%Y %I:%M %p')}",
        styles["Normal"]
    ))

    story.append(Paragraph("<br/>", styles["Normal"]))

    fields = [

        ("Full Name", user.get("fullname", "")),
        ("Email", user.get("email", "")),
        ("Mobile", user.get("mobile", "")),
        ("Location", user.get("location", "")),
        ("Village", user.get("village", "")),
        ("Language", user.get("language", "")),
        ("Crop Type", user.get("crop_type", "")),
        ("Soil Type", user.get("soil_type", "")),
        ("Farm Area", user.get("farm_area", "")),
        ("Irrigation", user.get("irrigation_type", "")),
        ("About", user.get("about", ""))

    ]

    for label, value in fields:

        if not value:
            value = "Not Added"

        story.append(
            Paragraph(f"<b>{label}:</b> {value}", styles["BodyText"])
        )

    pdf.build(story)

    buffer.seek(0)

    return send_file(

        buffer,

        as_attachment=True,

        download_name="AgriMitra_Profile.pdf",

        mimetype="application/pdf"

    )
@app.route("/change-password", methods=["GET", "POST"])
def change_password():

    if "email" not in session:
        return redirect("/login")

    if request.method == "POST":

        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if new_password != confirm_password:
            flash("New passwords do not match.", "error")
            return redirect("/change-password")

        email = session["email"]

        # Verify current password
        verify_url = (
            f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
        )

        verify_payload = {
            "email": email,
            "password": current_password,
            "returnSecureToken": True
        }

        verify = requests.post(verify_url, json=verify_payload)

        if verify.status_code != 200:
            flash("Current password is incorrect.", "error")
            return redirect("/change-password")

        id_token = verify.json()["idToken"]

        # Update password
        update_url = (
            f"https://identitytoolkit.googleapis.com/v1/accounts:update?key={FIREBASE_API_KEY}"
        )

        update_payload = {
            "idToken": id_token,
            "password": new_password,
            "returnSecureToken": False
        }

        update = requests.post(update_url, json=update_payload)

        if update.status_code == 200:
            flash("Password updated successfully.", "success")
            return redirect("/profile")

        flash("Unable to update password.", "error")

    return render_template("change_password.html")

if __name__ == "__main__":
    app.run(debug=True)