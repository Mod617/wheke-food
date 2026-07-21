# 1. INDISPENSABLE : Toujours en premier pour Gevent sur Railway
from gevent import monkey
monkey.patch_all()

from flask import Flask, request, jsonify, render_template, abort, redirect, url_for
import os
import uuid

# --- ADAPTATION FEDAPAY ROBUSTE ---
import fedapay

# Importation des extensions
from extensions import db, login_manager, socketio

# Importation du module de protection CSRF (Flask-WTF)
from flask_wtf.csrf import CSRFProtect

# Configuration de base
from werkzeug.utils import secure_filename
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

print("🚀 APPLICATION WHÈKÈ FOOD DÉMARRE")

# =====================================================================
# VALIDATION STRICTE DES SECRETS DE PRODUCTION (AUDIT SÉCURITÉ N°1)
# =====================================================================
FEDAPAY_SECRET = os.environ.get("FEDAPAY_SECRET_KEY")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

if not FEDAPAY_SECRET:
    raise RuntimeError("Erreur critique de sécurité : La variable d'environnement 'FEDAPAY_SECRET_KEY' est manquante.")
if not ADMIN_PASSWORD:
    raise RuntimeError("Erreur critique de sécurité : La variable d'environnement 'ADMIN_PASSWORD' est manquante.")
# =====================================================================

app = Flask(__name__)

# =====================================================================
# 🛡️ PROTECTION CSRF (AUDIT SÉCURITÉ N°9 - OWASP Top 10 A01:2021)
# =====================================================================
csrf = CSRFProtect(app)

# =========================
# CONFIGURATION
# =========================

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# SECRET_KEY obligatoire pour Flask-Login / sessions / jetons CSRF
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or os.urandom(24).hex()

# --- CONFIGURATION FEDAPAY (Standard API) ---
try:
    fedapay.api_key = FEDAPAY_SECRET
    fedapay.environment = "live"
    print("✅ FedaPay API configuré avec succès")
except Exception as e:
    print(f"⚠️ Erreur de configuration FedaPay : {e}")
# ---------------------------------------------

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

# =====================================================================
# 🔐 GESTION DYNAMIQUE DE LA REDIRECTION NON AUTORISÉE (LIVREUR vs ADMIN)
# =====================================================================
@login_manager.unauthorized_handler
def unauthorized():
    # Si la route demandée concerne un livreur (ex: /livreur/dashboard)
    if request.path.startswith("/livreur") or request.path.startswith("/api/livreur"):
        return redirect(url_for("livreur_login"))
    
    # Par défaut, rediriger vers la connexion Admin
    return redirect(url_for("admin_login"))

# =========================
# MODELS & USER LOADER
# =========================

with app.app_context():
    import models

@login_manager.user_loader
def load_user(user_id):
    from models import Admin, Livreur
    
    # 🔒 Identification explicite basée sur le préfixe
    if isinstance(user_id, str):
        if user_id.startswith("admin_"):
            try:
                return db.session.get(Admin, int(user_id.replace("admin_", "")))
            except ValueError:
                return None
        elif user_id.startswith("livreur_"):
            try:
                return db.session.get(Livreur, int(user_id.replace("livreur_", "")))
            except ValueError:
                return None

    # Fallback pour rétablir la rétrocompatibilité (si l'ID transmis est un entier simple)
    try:
        uid = int(user_id)
        admin = db.session.get(Admin, uid)
        if admin:
            return admin
        return db.session.get(Livreur, uid)
    except (ValueError, TypeError):
        return None

# =========================
# ROUTES
# =========================

@app.route("/contact", methods=["GET"])
def contact_page():
    return render_template("contact.html")

# Importation des routes principales
with app.app_context():
    import routes

# =========================
# INIT DB + AUTO-MIGRATION + ADMIN
# =========================

with app.app_context():
    from security import hash_password
    db.create_all()

    # 🛠️ AUTO-MIGRATION : Ajout automatique de la colonne manquante dans SQLite si elle n'existe pas
    try:
        with db.engine.connect() as conn:
            conn.execute(db.text("ALTER TABLE message ADD COLUMN livraison_id INTEGER;"))
            conn.commit()
            print("✅ Migration SQLite : Colonne 'livraison_id' ajoutée avec succès à la table 'message'.")
    except Exception as e:
        # Ignore l'erreur si la colonne existe déjà dans la base
        pass

    admin = models.Admin.query.filter_by(username="Mpenza").first()
    if not admin:
        db.session.add(models.Admin(
            username="Mpenza",
            password=hash_password(ADMIN_PASSWORD),
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