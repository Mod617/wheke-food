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

    # 🔒 Identification unique de session
    def get_id(self):
        return f"admin_{self.id}"


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

    # 🔒 Identification unique de session
    def get_id(self):
        return f"livreur_{self.id}"


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

    # 🔒 NOUVEAU : sécurité paiement (lie une transaction FedaPay à CETTE commande précise)
    fedapay_transaction_id = db.Column(db.String(50), nullable=True)
    derniere_relance = db.Column(db.DateTime, nullable=True)

    # 💳 NOUVEAU (FACTURATION) : état du paiement, indépendant du statut logistique.
    # "statut" mélange paiement ET livraison (recu → assigne → pris → livre...),
    # on ne peut donc plus savoir si une commande a été payée une fois qu'elle avance.
    paye = db.Column(db.Boolean, nullable=False, default=False)
    date_paiement = db.Column(db.DateTime, nullable=True)
    mode_paiement = db.Column(db.String(30), nullable=True)  # ex: mtn, moov, card (renvoyé par FedaPay)

    # 🧾 NOUVEAU (FACTURATION) : infos saisies par le client à la commande (optionnelles)
    # L'IFU béninois compte 13 chiffres.
    client_ifu = db.Column(db.String(13), nullable=True)
    client_raison_sociale = db.Column(db.String(200), nullable=True)

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


# =========================
# PUSH SUBSCRIPTIONS (Notifications)
# =========================

class PushSubscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    endpoint = db.Column(db.String(500), unique=True, nullable=False)
    p256dh = db.Column(db.String(300), nullable=False)
    auth = db.Column(db.String(300), nullable=False)

    date = db.Column(db.DateTime, default=datetime.utcnow)


# =========================
# 🧾 FACTURE NORMALISÉE (e-MECeF / DGI Bénin)
# =========================
# Une facture normalisée est un document FISCAL : elle ne se modifie pas et
# ne se supprime pas. En cas d'erreur, on émet une facture d'avoir (FA) puis
# une nouvelle facture (FV). C'est pour ça qu'elle a sa propre table, avec un
# instantané figé des lignes, au lieu d'être des colonnes sur Commande.

class Facture(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    commande_id = db.Column(
        db.Integer,
        db.ForeignKey("commande.id"),
        nullable=False,
        index=True
    )
    commande = db.relationship(
        "Commande",
        backref=db.backref("factures", lazy=True)  # pas de cascade : jamais de suppression en chaîne
    )

    # FV = facture de vente | FA = facture d'avoir (annulation / correction)
    type_facture = db.Column(db.String(2), nullable=False, default="FV")
    facture_origine_id = db.Column(db.Integer, db.ForeignKey("facture.id"), nullable=True)

    # en_attente → demandee → confirmee   (ou erreur / annulee)
    statut = db.Column(db.String(20), nullable=False, default="en_attente", index=True)
    tentatives = db.Column(db.Integer, nullable=False, default=0)
    derniere_erreur = db.Column(db.Text, nullable=True)

    # 👤 Client, figé au moment de l'émission
    client_ifu = db.Column(db.String(13), nullable=True)
    client_nom = db.Column(db.String(200), nullable=True)

    # 📦 Instantané des lignes facturées (JSON) + total TTC en FCFA
    lignes_json = db.Column(db.Text, nullable=True)
    total = db.Column(db.Integer, nullable=True)
    mode_paiement = db.Column(db.String(30), nullable=True)

    # 📡 Retour de l'API e-MCF
    uid = db.Column(db.String(64), unique=True, nullable=True)      # identifiant de la demande
    code_mecef = db.Column(db.String(60), nullable=True)            # code MECeF/DGI
    nim = db.Column(db.String(30), nullable=True)                   # NIM de l'e-MCF émetteur
    qr_code = db.Column(db.Text, nullable=True)                     # contenu du QR code
    compteurs = db.Column(db.String(60), nullable=True)
    date_mecef = db.Column(db.String(40), nullable=True)            # date/heure telle que renvoyée
    reponse_brute = db.Column(db.Text, nullable=True)               # JSON de confirmation (audit)

    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    date_confirmation = db.Column(db.DateTime, nullable=True)
