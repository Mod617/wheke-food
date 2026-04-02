from werkzeug.security import generate_password_hash, check_password_hash
import os

# =========================
# HASH MOT DE PASSE
# =========================

def hash_password(password):
    return generate_password_hash(password)


def verify_password(password, hashed):
    return check_password_hash(hashed, password)


# =========================
# VERIFICATION FICHIERS
# =========================

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "mp4",
    "webm",
    "mov"
}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# =========================
# ANTI HTTRACK
# =========================

BLOCKED_AGENTS = [
    "HTTrack",
    "wget",
    "curl",
    "libwww",
    "python-requests"
]


def block_scrapers(request):

    user_agent = request.headers.get("User-Agent", "")

    for agent in BLOCKED_AGENTS:
        if agent.lower() in user_agent.lower():
            return True

    return False

def check_password(password, hashed):
    return verify_password(password, hashed)