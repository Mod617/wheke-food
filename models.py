from extensions import db
from flask_login import UserMixin
import uuid
from datetime import datetime

# =========================
# ADMIN
# =========================

class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), default="admin")


# =========================
# LIVREUR
# =========================

class Livreur(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)

    nom = db.Column(db.String(100), nullable=False)
    telephone = db.Column(db.String(20), unique=True)
    password = db.Column(db.String(200))

    actif = db.Column(db.Boolean, default=True)
    note = db.Column(db.Float, default=5)

    # 🔥 NOUVEAU : POSITION GPS
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)

    # 🔥 NOUVEAU : STATUT
    en_route = db.Column(db.Boolean, default=False)
    disponible = db.Column(db.Boolean, default=True)

    livraisons = db.relationship("Livraison", backref="livreur", lazy=True)
    avis = db.relationship("Avis", backref="livreur", lazy=True)


# =========================
# CATEGORIES
# =========================

class Categorie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(50), unique=True, nullable=False)

    mets = db.relationship("Met", backref="categorie", lazy=True)


# =========================
# METS
# =========================

class Met(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(200), nullable=False)

    categorie_id = db.Column(db.Integer, db.ForeignKey("categorie.id"), nullable=False)

    media = db.Column(db.String(300), default="")
    prix = db.Column(db.Float, nullable=False, default=0)
    promo = db.Column(db.Integer, default=0)

    jours = db.Column(db.String(100), nullable=False)
    heure_debut = db.Column(db.String(20), nullable=False)
    heure_fin = db.Column(db.String(20), nullable=False)

    plats = db.relationship("Plat", backref="met", lazy=True, cascade="all, delete")


# =========================
# PLATS
# =========================

class Plat(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    met_id = db.Column(db.Integer, db.ForeignKey("met.id"), nullable=False)

    nom = db.Column(db.String(200), nullable=False)
    image = db.Column(db.String(300), default="")

    prix = db.Column(db.Float, nullable=False, default=0)

    items = db.relationship("CommandeItem", backref="plat", lazy=True)


# =========================
# COMMANDE
# =========================

# =========================
# COMMANDE
# =========================
class Commande(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    tracking_id = db.Column(
        db.String(20),
        unique=True,
        default=lambda: "WKF-" + str(uuid.uuid4()).replace("-", "")[:6].upper()
    )

    telephone = db.Column(db.String(20), nullable=False)
    adresse = db.Column(db.String(300), nullable=False)
    gps = db.Column(db.String(200))

    type_livraison = db.Column(db.String(20), nullable=False)

    prix_livraison = db.Column(db.Integer, nullable=True)
    total = db.Column(db.Integer, nullable=True)
    zone = db.Column(db.String(50), nullable=True)

    temps_estime = db.Column(db.Integer, default=25)
    statut = db.Column(db.String(50), default="recu")

    date = db.Column(db.DateTime, default=datetime.utcnow)

    # 🔥 NOUVEAU (IMPORTANT)
    livreur_id = db.Column(db.Integer, db.ForeignKey("livreur.id"), nullable=True)
    livreur = db.relationship("Livreur")


# =========================
# LIVRAISON
# =========================

class Livraison(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    commande_id = db.Column(db.Integer, db.ForeignKey("commande.id"), nullable=False)
    livreur_id = db.Column(db.Integer, db.ForeignKey("livreur.id"), nullable=False)

    # 🔥 STATUT GLOBAL
    statut = db.Column(db.String(50), default="assigne")
    # assigne → pris → en_route → arrive → livre → termine

    # 🔥 TEMPS RESTANT (minutes)
    temps_restant = db.Column(db.Integer, default=25)

    # 🔥 HEURE DE DÉPART
    heure_depart = db.Column(db.DateTime, nullable=True)

    # 🔥 HEURE D'ARRIVÉE
    heure_arrivee = db.Column(db.DateTime, nullable=True)

    # 🔥 CONFIRMATIONS
    livreur_confirme = db.Column(db.Boolean, default=False)
    admin_confirme = db.Column(db.Boolean, default=False)

    # 🔥 DATE CREATION
    date = db.Column(db.DateTime, default=datetime.utcnow)

    # ✅ RELATION CORRIGÉE (IMPORTANT)
    commande = db.relationship(
        "Commande",
        backref=db.backref("livraison", uselist=False)
    )


# =========================
# AVIS CLIENT
# =========================

class Avis(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    commande_id = db.Column(db.Integer, db.ForeignKey("commande.id"), nullable=False)
    livreur_id = db.Column(db.Integer, db.ForeignKey("livreur.id"), nullable=False)

    note = db.Column(db.Integer, nullable=False)
    commentaire = db.Column(db.String(300))

    date = db.Column(db.DateTime, default=datetime.utcnow)

class CommandeItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    commande_id = db.Column(db.Integer, db.ForeignKey("commande.id"), nullable=False)

    met_nom = db.Column(db.String(200))
    prix = db.Column(db.Float)
    quantite = db.Column(db.Integer)

    # 🔥 GARDE SI TU VEUX
    plat_id = db.Column(db.Integer, db.ForeignKey("plat.id"))

    # ✅ AJOUT IMPORTANT
    image = db.Column(db.String(300))  

# =========================
# ZONES DE LIVRAISON
# =========================

class Zone(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100))

    prix_standard = db.Column(db.Integer)
    prix_express = db.Column(db.Integer)

class Quartier(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    nom = db.Column(db.String(100), unique=True, nullable=False)

    zone_id = db.Column(db.Integer, db.ForeignKey("zone.id"), nullable=False)
    zone = db.relationship("Zone", backref="quartiers")    

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    tracking = db.Column(db.String(20), nullable=False)

    # 🔥 AJOUT CRUCIAL
    livraison_id = db.Column(db.Integer, db.ForeignKey("livraison.id"))

    sender = db.Column(db.String(20), nullable=False)  # client / livreur
    message = db.Column(db.Text, nullable=False)

    date = db.Column(db.DateTime, default=datetime.utcnow)