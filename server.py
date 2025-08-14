from flask import Flask, send_from_directory, jsonify
import os, json

app = Flask(__name__)

# ==== Chargement du mapping clubs (clubs.json) ====
def load_club_map():
    try:
        with open("clubs.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            return {str(k): v for k, v in data.items()}
    except Exception:
        return {}
CLUB_MAP = load_club_map()

# ==== Routes ====
@app.route("/")
def index():
    # Sert la page HTML principale
    return send_from_directory(".", "index.html")

@app.route("/club_map")
def club_map():
    # Donne le mapping clubs au front
    return jsonify(CLUB_MAP)

@app.route("/list_images")
def list_images():
    # Liste les images présentes dans /images
    images_dir = os.path.join(app.root_path, "images")
    files = []
    if os.path.exists(images_dir):
        files = sorted([
            f for f in os.listdir(images_dir)
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
        ])
    return jsonify(files)

@app.route("/images/<path:filename>")
def serve_image(filename):
    # Sert les fichiers du dossier /images
    return send_from_directory("images", filename)

if __name__ == "__main__":
    # Local: python server.py (Render utilisera gunicorn via le Procfile)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
