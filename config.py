import os

class Config:

    # clé secrète pour sécuriser les sessions
    SECRET_KEY = "cle_super_securisee_change_la_rapidement_458974521"

    # base de données SQLite
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "database.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # dossier upload images et vidéos
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static/uploads")

    # taille maximale upload (200MB pour vidéos)
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024

    # types de fichiers autorisés
    ALLOWED_EXTENSIONS = {
        "png",
        "jpg",
        "jpeg",
        "gif",
        "mp4",
        "webm",
        "mov"
    }

    # sécurité cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_SAMESITE = "Lax"