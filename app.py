# 1. INDISPENSABLE : Toujours en premier pour Gevent sur Railway
from gevent import monkey
monkey.patch_all()

from flask import Flask, request, jsonify, render_template, abort, redirect, url_for
import os
import uuid
from fedapay import FedaPay, Transaction # <--- Ajoute cette ligne

# Importation des extensions
from extensions import db, login_manager, socketio

# On retire Flask-Mail car Railway bloque les ports SMTP
from werkzeug.utils import secure_filename
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

print("🚀 APPLICATION WHÈKÈ FOOD DÉMARRE")

app = Flask(__name__)

# =========================
# CONFIG
# =========================

# =========================
# CONFIG
# =========================

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "super_secret_key")

# --- AJOUT FEDAPAY ICI ---
FedaPay.set_api_key(os.environ.get("FEDAPAY_SECRET_KEY", "sk_live_METS_TA_CLE_ICI"))
FedaPay.set_environment("live") 
# -------------------------

# DATABASE
db_url = os.environ.get("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url or (
    "sqlite:///" + os.path.join(BASE_DIR, "database.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads")
app.config["ALLOWED_EXTENSIONS"] = {"png", "jpg", "jpeg", "jfif", "webp"}

# =========================
# HEADERS & LIMITER
# =========================

@app.after_request
def add_headers(response):
    response.headers["Cache-Control"] = "public, max-age=300"
    return response

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per hour"],
    storage_uri="memory://" 
)

# =========================
# ANTI BOT SAFE
# =========================

@app.before_request
def block_bad_bots():
    user_agent = request.headers.get('User-Agent', '').lower()
    if not user_agent or "railway" in user_agent:
        return
    blocked = ['httrack', 'wget']
    if any(bot in user_agent for bot in blocked):
        abort(403)

# =========================
# 🔥 SOCKET.IO (CORRIGÉ POUR 502)
# =========================

if os.environ.get("RAILWAY_STATIC_URL") or os.environ.get("PORT"):
    print("🚀 MODE PRODUCTION (Railway) → gevent")
    socketio.init_app(
        app, 
        cors_allowed_origins="*", 
        async_mode="gevent",
        async_handlers=True,
        engineio_logger=False,
        ping_timeout=60,
        ping_interval=25
    )
else:
    print("🧪 MODE LOCAL → threading")
    socketio.init_app(app, cors_allowed_origins="*", async_mode="threading")

# =========================
# DOSSIER UPLOAD & INIT
# =========================

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = "admin_login"

# =========================
# MODELS & USER LOADER
# =========================

with app.app_context():
    import models

@login_manager.user_loader
def load_user(user_id):
    from models import Admin, Livreur
    user = db.session.get(Livreur, int(user_id))
    return user or db.session.get(Admin, int(user_id))

# =========================
# ROUTES
# =========================

@app.route("/contact", methods=["GET"])
def contact_page():
    return render_template("contact.html")

# Note : La route POST /contact n'est plus nécessaire car 
# le formulaire utilise maintenant directement l'API WhatsApp.

# Importation des routes principales
with app.app_context():
    import routes

# =========================
# INIT DB + ADMIN
# =========================

with app.app_context():
    from security import hash_password
    db.create_all()
    admin = models.Admin.query.filter_by(username="Mpenza").first()
    if not admin:
        db.session.add(models.Admin(
            username="Mpenza",
            password=hash_password(os.environ.get("ADMIN_PASSWORD", "change_me")),
            role="super_admin"
        ))
        db.session.commit()

# =========================
# ENTRYPOINT
# =========================

application = app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    socketio.run(
        app,
        host="0.0.0.0",
        port=port
    )