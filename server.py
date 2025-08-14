from flask import Flask, send_from_directory, render_template_string
import json
import os

app = Flask(__name__, static_folder='images')

# Charger le HTML
with open("index.html", "r", encoding="utf-8") as f:
    index_html = f.read()

# Charger les clubs
with open("clubs.json", "r", encoding="utf-8") as f:
    clubs = json.load(f)

@app.route("/")
def home():
    return render_template_string(index_html, clubs=clubs)

# Route pour les images
@app.route("/images/<path:filename>")
def images(filename):
    return send_from_directory("images", filename)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
