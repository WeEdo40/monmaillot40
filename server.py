import os, json
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, Response
from urllib.parse import urljoin
import stripe

BASE_DIR = Path(__file__).resolve().parent
IMAGES_DIR = BASE_DIR / "images"
ORDERS_FILE = BASE_DIR / "orders.json"
CLUBS_FILE = BASE_DIR / "clubs.json"

app = Flask(__name__)

# ====== STRIPE (définir ces variables dans Render -> Environment) ======
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")               # sk_test_... / sk_live_...
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY")  # pk_test_...
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")    # whsec_...
ADMIN_KEY = os.environ.get("ADMIN_KEY", "admin")                   # clé simple pour /admin

# ====== ROUTES STATIC / CATALOG ======
@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/images/<path:filename>")
def images(filename):
    return send_from_directory(IMAGES_DIR, filename)

@app.route("/list_images")
def list_images():
    exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    files = []
    if IMAGES_DIR.exists():
        for p in sorted(IMAGES_DIR.iterdir()):
            if p.is_file() and p.suffix.lower() in exts:
                files.append(p.name)
    return jsonify(files)

@app.route("/club_map")
def club_map():
    if CLUBS_FILE.exists():
        try:
            return jsonify(json.loads(CLUBS_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    # fallback si pas de fichier
    return jsonify({
        "1": "PSG",
        "2": "Real Madrid",
        "1.1": "Allemagne",
        "1.2": "France"
    })

# ====== STRIPE CHECKOUT ======
@app.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    if not stripe.api_key:
        return jsonify({"error":"Stripe non configuré (STRIPE_SECRET_KEY manquante)."}), 500

    data = request.get_json(force=True)
    items = data.get("items", [])
    shipping = data.get("shipping", {})

    # Panier -> line_items
    line_items = []
    subtotal_cents = 0
    for it in items:
        unit = int(float(it["unit_price"]) * 100)
        qty = int(it["qty"])
        subtotal_cents += unit * qty

        img = it.get("image","")
        if img.startswith("/"):
            img = urljoin(request.host_url, img.lstrip("/"))

        line_items.append({
            "price_data": {
                "currency": "eur",
                "unit_amount": unit,
                "product_data": {
                    "name": it["name"],
                    "images": [img],
                    "metadata": {
                        "id": it.get("id",""),
                        "size": it.get("size",""),
                        "flock": it.get("flock","")
                    }
                }
            },
            "quantity": qty
        })

    # Frais de port (même logique que le front)
    method = (shipping.get("method") or "std").lower()
    if subtotal_cents >= 6000:
        shipping_cents = 0
    else:
        shipping_cents = 999 if method == "exp" else 499

    if shipping_cents > 0:
        line_items.append({
            "price_data": {
                "currency": "eur",
                "unit_amount": shipping_cents,
                "product_data": { "name": "Livraison" }
            },
            "quantity": 1
        })

    success_url = urljoin(request.host_url, "success?session_id={CHECKOUT_SESSION_ID}")
    cancel_url  = urljoin(request.host_url, "cancel")

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=line_items,
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email = shipping.get("email") or None,
            shipping_address_collection={"allowed_countries":["FR","BE","DE","ES","IT","PT","NL"]},
            metadata={
                "shipping_name": shipping.get("name",""),
                "shipping_addr": shipping.get("addr",""),
                "shipping_city": shipping.get("city",""),
                "shipping_zip":  shipping.get("zip",""),
                "shipping_country": shipping.get("country","France"),
                "shipping_method": method,
            }
        )
        return jsonify({"url": session.url})
    except Exception as e:
        print("Stripe error:", e)
        return jsonify({"error": str(e)}), 400

@app.route("/success")
def success():
    return (
        "<h1>Paiement confirmé ✅</h1><p>Merci pour votre commande. "
        "Vous allez recevoir un e-mail de confirmation. "
        "<br><a href='/#produits'>Retour à la boutique</a></p>"
    )

@app.route("/cancel")
def cancel():
    return (
        "<h1>Paiement annulé</h1><p>Vous pouvez revenir au panier pour réessayer."
        "<br><a href='/#produits'>Retour à la boutique</a></p>"
    )

# ====== WEBHOOK STRIPE ======
@app.route("/webhook", methods=["POST"])
def webhook():
    if not STRIPE_WEBHOOK_SECRET:
        event = request.get_json(force=True)   # dev only
    else:
        payload = request.data
        sig_header = request.headers.get("Stripe-Signature", "")
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        except Exception as e:
            print("Webhook error:", e)
            return "", 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        line_items = stripe.checkout.Session.list_line_items(session["id"], limit=100)

        order = {
            "id": session["id"],
            "created": session["created"],
            "email": (session.get("customer_details") or {}).get("email") or session.get("customer_email"),
            "amount_total": session["amount_total"],
            "currency": session["currency"],
            "shipping": {
                "name":    (session.get("metadata") or {}).get("shipping_name",""),
                "addr":    (session.get("metadata") or {}).get("shipping_addr",""),
                "city":    (session.get("metadata") or {}).get("shipping_city",""),
                "zip":     (session.get("metadata") or {}).get("shipping_zip",""),
                "country": (session.get("metadata") or {}).get("shipping_country",""),
                "method":  (session.get("metadata") or {}).get("shipping_method",""),
            },
            "items": []
        }
        for li in line_items["data"]:
            order["items"].append({
                "description": li["description"],
                "quantity": li["quantity"],
                "amount_subtotal": li["amount_subtotal"]
            })

        # Sauvegarde
        existing = []
        if ORDERS_FILE.exists():
            try:
                existing = json.loads(ORDERS_FILE.read_text(encoding="utf-8") or "[]")
            except Exception:
                existing = []
        existing.append(order)
        ORDERS_FILE.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        print("✅ Commande enregistrée:", order["id"])

    return "", 200

# ====== ADMIN COMMANDES ======
@app.route("/admin/orders")
def admin_orders():
    key = request.args.get("key", "")
    if key != ADMIN_KEY:
        return Response("Forbidden", 403)
    data = []
    if ORDERS_FILE.exists():
        data = json.loads(ORDERS_FILE.read_text(encoding="utf-8") or "[]")
    rows = []
    for o in reversed(data):
        rows.append(
            f"<tr><td>{o['id']}</td>"
            f"<td>{o.get('email','')}</td>"
            f"<td>{o['amount_total']/100:.2f} {o['currency'].upper()}</td>"
            f"<td>{o['shipping']['name']} — {o['shipping']['addr']}, {o['shipping']['zip']} {o['shipping']['city']}, {o['shipping']['country']} ({o['shipping']['method']})</td>"
            f"<td><pre style='white-space:pre-wrap'>{json.dumps(o['items'], ensure_ascii=False, indent=2)}</pre></td></tr>"
        )
    html = f"""
    <h1>Commandes</h1>
    <table border="1" cellpadding="6" cellspacing="0">
      <thead><tr><th>Session</th><th>Email</th><th>Total</th><th>Livraison</th><th>Articles</th></tr></thead>
      <tbody>{''.join(rows) or '<tr><td colspan=5>Aucune commande</td></tr>'}</tbody>
    </table>
    """
    return html

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
