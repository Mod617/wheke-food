from flask import Flask, request, jsonify, render_template, abort
import os
import uuid

from extensions import db, login_manager, socketio

from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

print("APPLICATION DEMARRE")

app = Flask(__name__)

# =========================
# CONFIG
# =========================

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "super_secret_key")

# DATABASE (Railway)
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
# HEADERS
# =========================

@app.after_request
def add_headers(response):
    response.headers["Cache-Control"] = "public, max-age=300"
    return response

# =========================
# LIMITER
# =========================

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per hour"]
)

# =========================
# MAIL
# =========================

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'whekefood@gmail.com'
app.config['MAIL_PASSWORD'] = os.environ.get("MAIL_PASSWORD")

mail = Mail(app)

# =========================
# ✅ ANTI BOT CORRIGÉ (IMPORTANT)
# =========================

@app.before_request
def block_bad_bots():
    user_agent = request.headers.get('User-Agent', '').lower()

    # ✅ IMPORTANT : ne pas bloquer si vide (Railway)
    if not user_agent:
        return

    # ✅ autoriser Railway / health checks
    if "railway" in user_agent:
        return

    # ❌ bots vraiment dangereux seulement
    blocked = ['httrack', 'wget']

    if any(bot in user_agent for bot in blocked):
        abort(403)

# =========================
# SOCKET.IO
# =========================

socketio.init_app(
    app,
    cors_allowed_origins="*",
    async_mode="gevent"
)

# =========================
# DOSSIER UPLOAD
# =========================

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# =========================
# INIT
# =========================

db.init_app(app)
login_manager.init_app(app)

login_manager.login_view = "admin_login"

# =========================
# IMPORT MODELS
# =========================

with app.app_context():
    import models

# =========================
# USER LOADER
# =========================

@login_manager.user_loader
def load_user(user_id):
    from models import Admin, Livreur

    user = db.session.get(Livreur, int(user_id))
    return user or db.session.get(Admin, int(user_id))

# =========================
# UTILS
# =========================

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]

# =========================
# ROUTES
# =========================

@app.route("/contact", methods=["GET"])
def contact_page():
    return render_template("contact.html")

@app.route("/contact", methods=["POST"])
@limiter.limit("5 per minute")
def contact():

    if not request.is_json:
        return jsonify({"success": False}), 400

    data = request.get_json()

    nom = data.get("nom")
    email = data.get("email")
    message = data.get("message")

    if not nom or not email or not message:
        return jsonify({"success": False})

    try:
        msg = Message(
            subject=f"📩 {nom}",
            sender=app.config['MAIL_USERNAME'],
            recipients=["whekefood@gmail.com"]
        )

        msg.body = f"{nom}\n{email}\n\n{message}"

        mail.send(msg)

        return jsonify({"success": True})

    except Exception as e:
        print("MAIL ERROR:", e)
        return jsonify({"success": False})

@app.route("/upload", methods=["POST"])
@limiter.limit("10 per minute")
def upload_file():

    if 'file' not in request.files:
        return jsonify({"error": "Aucun fichier"}), 400

    file = request.files['file']

    if file.filename == "":
        return jsonify({"error": "Nom invalide"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_name = str(uuid.uuid4()) + "_" + filename

        file_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
        file.save(file_path)

        return jsonify({"success": True, "filename": unique_name})

    return jsonify({"error": "Format non autorisé"}), 400

# =========================
# IMPORT ROUTES PRINCIPALES
# =========================

with app.app_context():
    import routes

# =========================
# INIT DB + ADMIN
# =========================

with app.app_context():
    from security import hash_password
    import models

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
# ENTRYPOINT POUR GUNICORN
# =========================

application = app

# =========================
# RUN LOCAL
# =========================

if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )