from flask import Flask, send_from_directory, jsonify
import os, json

IMAGES_DIR = "images"
CLUBS_FILE = "clubs.json"

app = Flask(__name__, static_folder=".", static_url_path="")

def load_club_map():
    if os.path.exists(CLUBS_FILE):
        with open(CLUBS_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                # Convertit toutes les clés en str (au cas où)
                return {str(k): v for k, v in data.items()}
            except Exception:
                pass
    # Fallback par défaut si clubs.json absent ou invalide
    return {
        "1": "PSG",
        "2": "Real Madrid",
        "1.1": "Allemagne",
        "1.2": "France"
    }

@app.route("/")
def home():
    return send_from_directory(".", "index.html")

@app.route("/images/<path:filename>")
def images(filename):
    return send_from_directory(IMAGES_DIR, filename)

@app.route("/list_images")
def list_images():
    os.makedirs(IMAGES_DIR, exist_ok=True)
    files = sorted([f for f in os.listdir(IMAGES_DIR)
                    if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))])
    return jsonify(files)

@app.route("/club_map")
def club_map():
    return jsonify(load_club_map())

if __name__ == "__main__":
    os.makedirs(IMAGES_DIR, exist_ok=True)
    print("Serveur démarré sur http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
