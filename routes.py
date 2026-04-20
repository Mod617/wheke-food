from flask import render_template, request, redirect, jsonify, url_for, flash, abort
from flask import current_app as app
from datetime import datetime
from flask_socketio import emit, join_room

from extensions import db, login_manager, socketio

import models

from security import hash_password, verify_password, check_password
from flask_login import login_user, login_required, logout_user, current_user
import os
from sqlalchemy import func
import uuid
import math
import qrcode
import io
from flask import send_file

def distance_km(lat1, lon1, lat2, lon2):
    R = 6371  # km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


# =========================
# TRACKING UNIQUE
# =========================

def generer_tracking():
    return "WKF-" + str(uuid.uuid4()).replace("-", "")[:6].upper()

# =========================
# CONSTANTES
# =========================

JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

CATEGORIES = {
    "Repas": 1,
    "Dessert": 2,
    "Jus": 3
}

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "jfif"}

# =========================
# UTILITAIRES
# =========================

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# =========================
# CALCUL DISPONIBILITE
# =========================

def calcul_disponibilite(met):
    now = datetime.now()
    jour_actuel_index = now.weekday()
    heure_actuelle = now.strftime("%H:%M")

    # ✅ NETTOYAGE SAFE (ANTI-BUG)
    jours_met = [j.strip() for j in (met.jours or "").split(",") if j.strip() in JOURS]

    # 🔥 Si aucun jour valide → fallback
    if not jours_met:
        met.badge = "later"
        return "Non disponible"

    prochain_jour_index = None

    for j in jours_met:
        index = JOURS.index(j)
        diff = (index - jour_actuel_index) % 7

        if prochain_jour_index is None or diff < prochain_jour_index:
            prochain_jour_index = diff

    # 🔥 DOUBLE SÉCURITÉ
    if prochain_jour_index is None:
        met.badge = "later"
        return "Non disponible"

    # 🔥 BADGES + TEXTE
    if prochain_jour_index == 0:
        if met.heure_debut <= heure_actuelle <= met.heure_fin:
            met.badge = "now"
            return "Disponible maintenant"
        else:
            met.badge = "today"
            return f"Aujourd'hui à {met.heure_debut}"

    elif prochain_jour_index == 1:
        met.badge = "tomorrow"
        return "Disponible demain"

    else:
        met.badge = "later"
        return f"Disponible dans {prochain_jour_index} jours"

def est_expire(met):
    now = datetime.now()
    jour_actuel = JOURS[now.weekday()]
    heure_actuelle = now.time()

    jours_met = met.jours.split(",")

    # ✅ Si ce n'est PAS aujourd'hui → NE PAS masquer
    if jour_actuel not in jours_met:
        return False

    # ✅ Si c'est aujourd'hui → vérifier l'heure
    h_fin = datetime.strptime(met.heure_fin, "%H:%M").time()

    if heure_actuelle > h_fin:
        return True

    return False

def statut_met_admin(met):
    now = datetime.now()
    jour_actuel = JOURS[now.weekday()]
    heure_actuelle = now.time()

    jours_met = met.jours.split(",")

    # 🔸 Si pas aujourd’hui
    if jour_actuel not in jours_met:
        return "a_venir"

    h_debut = datetime.strptime(met.heure_debut, "%H:%M").time()
    h_fin = datetime.strptime(met.heure_fin, "%H:%M").time()

    if heure_actuelle < h_debut:
        return "a_venir"
    elif h_debut <= heure_actuelle <= h_fin:
        return "actif"
    else:
        return "expire"

# =========================
# PAGE CLIENT
# =========================
@app.route("/")
def accueil():
    now = datetime.now()
    jour_actuel_index = now.weekday()

    mets = models.Met.query.all()

    repas = []
    desserts = []
    jus = []

    for m in mets:

        # 🔥 SUPPRESSION VISUELLE
        if est_expire(m):
            continue

        # ✅ NETTOYAGE SAFE DES JOURS (ANTI-BUG)
        jours_met = [
            j.strip()
            for j in (m.jours or "").split(",")
            if j.strip() in JOURS
        ]

        # 🔥 Si aucun jour valide → skip
        if not jours_met:
            continue

        # 🔥 trouver prochain jour valide
        prochain_jour_index = None

        for j in jours_met:
            index = JOURS.index(j)
            diff = (index - jour_actuel_index) % 7

            if prochain_jour_index is None or diff < prochain_jour_index:
                prochain_jour_index = diff

        if prochain_jour_index is None:
            continue

        # 🔥 calcul dispo + badge
        m.disponibilite = calcul_disponibilite(m)

        # 🔥 PRIORITÉ
        if m.badge == "now":
            m.priorite = 0
        elif m.badge == "today":
            m.priorite = 1
        elif m.badge == "tomorrow":
            m.priorite = 2
        else:
            m.priorite = 3 + prochain_jour_index

        # 🔥 classement par catégorie
        if m.categorie_id == 1:
            repas.append(m)
        elif m.categorie_id == 2:
            desserts.append(m)
        elif m.categorie_id == 3:
            jus.append(m)

    # 🔥 TRI FINAL
    repas.sort(key=lambda x: x.priorite)
    desserts.sort(key=lambda x: x.priorite)
    jus.sort(key=lambda x: x.priorite)

    return render_template(
        "base.html",
        repas=repas,
        desserts=desserts,
        jus=jus
    )


        
 

# =========================
# 🚀 NOUVELLE COMMANDE (JSON)
# =========================
@app.route("/commander", methods=["POST"])
def commander():
    import requests
    import uuid
    import os

    data = request.get_json()
    telephone = data.get("telephone")
    adresse = data.get("adresse", "")
    gps = data.get("gps", "")
    panier = data.get("panier", [])
    livraison = data.get("livraison", "standard")
    zone_nom = data.get("zone", "")

    if not telephone or not panier:
        return jsonify({"success": False, "message": "Téléphone ou panier vide"})

    # 1. CALCUL DU TOTAL
    total_plats = 0
    for item in panier:
        met = models.Met.query.get(item.get("id"))
        if met:
            prix_reel = met.prix - (met.prix * met.promo / 100) if met.promo > 0 else met.prix
            total_plats += round(prix_reel) * int(item.get("qte", 1))

    prix_livraison = 0
    if zone_nom:
        from sqlalchemy import func
        z_db = models.Zone.query.filter(func.lower(models.Zone.nom) == zone_nom.strip().lower()).first()
        if z_db:
            prix_livraison = z_db.prix_standard if livraison == "standard" else z_db.prix_express
    
    total_final = total_plats + prix_livraison
    track_id = str(uuid.uuid4())[:8].upper() 

    # 2. ENREGISTREMENT EN BASE DE DONNÉES
    try:
        commande = models.Commande(
            telephone=telephone, adresse=adresse, gps=gps,
            type_livraison=livraison, statut="attente_paiement",
            tracking_id=track_id, prix_livraison=prix_livraison, total=total_final
        )
        db.session.add(commande)
        db.session.commit()

        for item in panier:
            met = models.Met.query.get(item.get("id"))
            if met:
                p = round(met.prix - (met.prix * met.promo / 100) if met.promo > 0 else met.prix)
                db.session.add(models.CommandeItem(
                    commande_id=commande.id, met_nom=met.nom,
                    prix=p, quantite=int(item.get("qte", 1)), image=met.media
                ))
        db.session.commit()
    except Exception as e:
        return jsonify({"success": False, "message": "Erreur Base de données"})

    # 3. APPEL DIRECT API FEDAPAY
    # On vérifie Railway d'abord, puis la config Flask
    api_key = os.getenv('FEDAPAY_SECRET_KEY') or app.config.get('FEDAPAY_SECRET_KEY')
    env = os.getenv('FEDAPAY_ENVIRONMENT') or app.config.get('FEDAPAY_ENVIRONMENT', 'sandbox')

    base_url = "https://api.fedapay.com/v1"
    if env == "sandbox":
        base_url = "https://sandbox-api.fedapay.com/v1"

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    payload = {
        "amount": int(total_final),
        "currency": {"iso": "XOF"},
        "description": f"Commande {track_id}",
        "customer": {
            "firstname": "Client", "lastname": telephone,
            "email": "paiement@whekefood.com",
            "phone_number": {"number": telephone, "country": "bj"}
        },
        "callback_url": url_for('valider_paiement_final', tracking_id=track_id, _external=True)
    }

    try:
        req = requests.post(f"{base_url}/transactions", json=payload, headers=headers)
        res = req.json()
        
        if req.status_code not in [200, 201]:
            # C'est ici que l'erreur d'authentification est captée
            return jsonify({"success": False, "message": f"FedaPay API: {res.get('message', 'Erreur inconnue')}"})

        trans_id = res['v1/transaction']['id']
        token_req = requests.post(f"{base_url}/transactions/{trans_id}/token", headers=headers)
        token_res = token_req.json()

        return jsonify({
            "success": True, 
            "redirect_url": token_res['v1/token']['url']
        })

    except Exception as e:
        return jsonify({"success": False, "message": "Erreur de connexion FedaPay"})

@app.route("/valider-paiement-final")
def valider_paiement_final():
    import requests
    import os
    id_transaction = request.args.get('id')
    tracking_id = request.args.get('tracking_id')

    if not id_transaction:
        return redirect("/")

    api_key = os.getenv('FEDAPAY_SECRET_KEY') or app.config.get('FEDAPAY_SECRET_KEY')
    env = os.getenv('FEDAPAY_ENVIRONMENT') or app.config.get('FEDAPAY_ENVIRONMENT', 'sandbox')

    base_url = "https://api.fedapay.com/v1"
    if env == "sandbox":
        base_url = "https://sandbox-api.fedapay.com/v1"

    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        # Vérification manuelle du statut sans utiliser le SDK
        req = requests.get(f"{base_url}/transactions/{id_transaction}", headers=headers)
        res = req.json()
        
        # Structure de réponse FedaPay : res['v1/transaction']['status']
        status = res.get('v1/transaction', {}).get('status')

        if status == 'approved':
            commande = models.Commande.query.filter_by(tracking_id=tracking_id).first()
            if commande:
                commande.statut = "recu"
                db.session.commit()
                # On redirige vers une page de succès ou le dashboard
                return redirect(f"/suivi/{tracking_id}?status=success")
        
        return redirect("/")
    except Exception as e:
        print(f"Erreur validation : {e}")
        return redirect("/")
# =========================
# LOGIN ADMIN
# =========================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        admin = models.Admin.query.filter_by(username=username).first()

        if admin and verify_password(password, admin.password):
            login_user(admin)
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Nom d'utilisateur ou mot de passe incorrect")

    return render_template("admin_login.html")

# =========================
# DASHBOARD ADMIN
# =========================

@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    commandes = models.Commande.query.order_by(models.Commande.date.desc()).all()

    for c in commandes:
        c.items = models.CommandeItem.query.filter_by(commande_id=c.id).all()

        livraison = models.Livraison.query.filter_by(commande_id=c.id).first()

        if livraison:
            c.livraison = livraison
            c.livreur = models.Livreur.query.get(livraison.livreur_id)
        else:
            c.livraison =  None
            c.livreur = None

    ventes_jour = db.session.query(func.count(models.Commande.id)).scalar()

    plats = models.Met.query.all()

    # 🔥 compteur livreurs
    livreurs = models.Livreur.query.all()
    for l in livreurs:
        l.nb_commandes = models.Livraison.query.filter_by(
            livreur_id=l.id
        ).count()

    for p in plats:
        p.statut_admin = statut_met_admin(p)

    return render_template(
        "admin_dashboard.html",
        commandes=commandes,
        ventes_jour=ventes_jour,
        plats=plats,
        livreurs=livreurs,
        jours=JOURS,
        top_plats=[]
    )

# =========================
# AJOUT MET
# =========================

@app.route("/admin/add_met", methods=["POST"])
@login_required
def add_met():
    nom = request.form.get("nom")
    categorie_name = request.form.get("categorie_name")
    categorie_id = CATEGORIES.get(categorie_name)

    prix = float(request.form.get("prix", 0))
    promo = request.form.get("promo") or 0
    promo = int(promo)

    jours = ",".join(request.form.getlist("jours"))
    heure_debut = request.form.get("heure_debut")
    heure_fin = request.form.get("heure_fin")

    file = request.files.get("media")
    filename = ""

    if file and allowed_file(file.filename):
        ext = file.filename.rsplit(".", 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    met = models.Met(
        nom=nom,
        categorie_id=categorie_id,
        prix=prix,
        promo=promo,
        media=filename,
        jours=jours,
        heure_debut=heure_debut,
        heure_fin=heure_fin
    )

    db.session.add(met)
    db.session.commit()

    flash("Plat ajouté avec succès")
    return redirect(url_for("admin_dashboard"))

# =========================
# EDIT MET
# =========================

@app.route("/admin/edit_met/<int:met_id>", methods=["POST"])
@login_required
def edit_met(met_id):

    met = models.Met.query.get_or_404(met_id)

    # ✅ Récupération
    nom = request.form.get("nom")

    categorie_name = request.form.get("categorie_name")
    categorie_id = CATEGORIES.get(categorie_name) if categorie_name else met.categorie_id

    prix = float(request.form.get("prix", met.prix))
    promo = int(request.form.get("promo", met.promo))

    jours_list = request.form.getlist("jours")
    jours = ",".join(jours_list) if jours_list else met.jours

    heure_debut = request.form.get("heure_debut") or met.heure_debut
    heure_fin = request.form.get("heure_fin") or met.heure_fin

    # ✅ IMAGE (important)
    file = request.files.get("media")
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit(".", 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        met.media = filename

    # ✅ Update sécurisé
    met.nom = nom
    met.categorie_id = categorie_id
    met.prix = prix
    met.promo = promo
    met.jours = jours
    met.heure_debut = heure_debut
    met.heure_fin = heure_fin

    db.session.commit()

    flash("Plat modifié avec succès ✅")
    return redirect(url_for("admin_dashboard"))

 

# =========================
# DELETE MET
# =========================

@app.route("/admin/delete_met/<int:met_id>", methods=["POST"])
@login_required
def delete_met(met_id):
    met = models.Met.query.get_or_404(met_id)

    if met.media:
        path = os.path.join(app.config["UPLOAD_FOLDER"], met.media)
        if os.path.exists(path):
            os.remove(path)

    db.session.delete(met)
    db.session.commit()

    flash("Plat supprimé avec succès")
    return redirect(url_for("admin_dashboard"))

# =========================
# LOGOUT
# =========================

@app.route("/admin/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("admin_login"))



@app.route("/admin/data")
def admin_data():
    from models import Met, Commande

    plats = Met.query.all()
    commandes = Commande.query.all()

    return jsonify({
        "plats": [
            {
                "id": m.id,
                "nom": m.nom,
                "prix": m.prix,
                "promo": m.promo,
                "jours": m.jours,
                "heure_debut": m.heure_debut,
                "heure_fin": m.heure_fin,
                "media": m.media
            } for m in plats
        ],
        "commandes": [
            {
                "id": c.id,
                "tracking_id": c.tracking_id,
                "statut": c.statut
            } for c in commandes
        ],
        "total_plats": len(plats),
        "total_commandes": len(commandes)
    })

# =========================
# PAGE COMMANDE
# =========================
@app.route("/commande")
def page_commande():
    return render_template("commande.html")

# =========================
# 🔥 AJOUT PRIX LIVRAISON
# =========================
@app.route("/admin/set_prix/<int:commande_id>", methods=["POST"])
@login_required
def set_prix(commande_id):

    commande = models.Commande.query.get_or_404(commande_id)

    prix = int(request.form.get("prix", 0))

    # 🔥 calcul total plats
    items = models.CommandeItem.query.filter_by(commande_id=commande.id).all()

    total_plats = sum(i.prix * i.quantite for i in items)

    # 🔥 update
    commande.prix_livraison = prix
    commande.total = total_plats + prix

    db.session.commit()

    return redirect(url_for("admin_dashboard"))

# =========================
# 🔎 SUIVI COMMANDE
# =========================
@app.route("/api/suivi/<tracking_id>")
def api_suivi(tracking_id):

    commande = models.Commande.query.filter_by(tracking_id=tracking_id).first()

    if not commande:
        return jsonify({"error": "Commande introuvable"}), 404

    livraison = models.Livraison.query.filter_by(commande_id=commande.id).first()

    # 🟡 PAS ENCORE DE LIVREUR
    if not livraison:
        return jsonify({
            "statut": commande.statut,
            "message": "⏳ En attente d’un livreur...",
            "temps_restant": None,
            "livreur": None
        })

    livreur = models.Livreur.query.get(livraison.livreur_id)

    # 🔐 Sécurité
    if not livreur:
        return jsonify({
            "statut": livraison.statut,
            "message": "⚠️ Livreur introuvable",
            "temps_restant": livraison.temps_restant,
            "livreur": None
        })

    # 🔥 FORMAT TELEPHONE (IMPORTANT POUR WHATSAPP)
    telephone = None
    if livreur.telephone:
        telephone = livreur.telephone.replace("+", "").replace(" ", "")

    # =========================
    # 🔥 MESSAGE INTELLIGENT
    # =========================
    if livraison.statut == "assigne":
        message = "📦 Un livreur a été assigné"

    elif livraison.statut == "pris":
        message = "📦 Le livreur a pris votre commande"

    elif livraison.statut == "en_route":
        if livraison.temps_restant is not None:
            message = f"🚀 En route - ⏱ {livraison.temps_restant} min restantes"
        else:
            message = "🚀 Le livreur est en route"

    elif livraison.statut == "arrive":
        message = "📍 Le livreur est arrivé ! Sortez récupérer votre commande 🍔"

    elif livraison.statut == "livre":
        message = "✅ Commande livrée avec succès. Merci 🙏"

    else:
        message = livraison.statut or "Statut inconnu"

    # =========================
    # ✅ JSON FINAL CORRIGÉ
    # =========================
    return jsonify({
        "statut": livraison.statut,
        "message": message,
        "temps_restant": getattr(livraison, "temps_restant", None),
        "livreur": {
            "nom": livreur.nom,
            "telephone": telephone,  # 🔥 IMPORTANT
            "lat": livreur.lat,
            "lng": livreur.lng
        }
    })

@app.route("/admin/assign_livreur", methods=["POST"])
@login_required
def assign_livreur():

    commande_id = request.form.get("commande_id")
    livreur_id = request.form.get("livreur_id")

    if not commande_id or not livreur_id:
        return redirect(url_for("admin_dashboard"))

    commande = models.Commande.query.get_or_404(commande_id)
    nouveau_livreur = models.Livreur.query.get_or_404(livreur_id)

    # 🔍 vérifier si une livraison existe déjà
    livraison = models.Livraison.query.filter_by(commande_id=commande.id).first()

    if livraison:
        # 🔁 récupérer ancien livreur
        ancien_livreur = models.Livreur.query.get(livraison.livreur_id)

        # 🔓 rendre l'ancien livreur disponible
        if ancien_livreur and ancien_livreur.id != nouveau_livreur.id:
            ancien_livreur.disponible = True

        # 🔁 remplacer par le nouveau
        livraison.livreur_id = nouveau_livreur.id

    else:
        # 🆕 créer livraison
        livraison = models.Livraison(
            commande_id=commande.id,
            livreur_id=nouveau_livreur.id,
            statut="assigne"
        )
        db.session.add(livraison)

    # 🔥 statut commande
    commande.statut = "assigne"

    # 🔒 nouveau livreur occupé
    nouveau_livreur.disponible = False

    db.session.commit()

    return redirect(url_for("admin_dashboard"))

# =========================
# 🔥 JOIN ROOM (MANQUANT)
# =========================
@socketio.on("join_tracking")
def on_join(data):
    tracking = data.get("tracking")

    if tracking:
        join_room(tracking)
        print(f"✅ Client rejoint la room : {tracking}")

# =========================
# 📍 UPDATE POSITION LIVREUR
# =========================
# =========================
@app.route("/api/livreur/position", methods=["POST"])
@login_required
def update_position():

    import requests

    data = request.get_json()

    lat = data.get("lat")
    lng = data.get("lng")
    livraison_id = data.get("livraison_id")

    livreur = current_user

    # 🔐 SÉCURITÉ
    if not hasattr(livreur, "telephone"):
        return jsonify({
            "success": False,
            "error": "Accès refusé (non livreur)"
        }), 403

    if lat is None or lng is None:
        return jsonify({
            "success": False,
            "error": "Coordonnées manquantes"
        }), 400

    livraison = db.session.get(models.Livraison, livraison_id)

    if livraison:

        commande = db.session.get(models.Commande, livraison.commande_id)

        now = datetime.utcnow()

        # =========================
        # 🚀 PREMIER LANCEMENT
        # =========================
        if livraison.statut != "en_route":
            livraison.statut = "en_route"
            livraison.heure_depart = now

        # =========================
        # 🚴 VITESSE RÉELLE
        # =========================

        old_lat = livreur.lat
        old_lng = livreur.lng
        old_time = getattr(livreur, "last_update", None)

        livreur.lat = lat
        livreur.lng = lng
        livreur.last_update = now
        livreur.en_route = True

        vitesse = 25  # fallback
        moved = False

        if old_lat and old_lng and old_time:

            dist_moved = distance_km(old_lat, old_lng, lat, lng)
            time_diff = (now - old_time).total_seconds() / 3600

            if dist_moved > 0.01:  # ~10m
                moved = True

            if time_diff > 0:
                calc_vitesse = dist_moved / time_diff

                if 1 < calc_vitesse < 80:
                    vitesse = calc_vitesse

        print(f"🚴 Vitesse: {vitesse:.2f} km/h | moved={moved}")

        # =========================
        # 🔥 ETA OSRM OPTIMISÉ
        # =========================

        dist_km = None
        eta = livraison.temps_restant

        last_eta_update = getattr(livraison, "last_eta_update", None)

        should_update_eta = False

        if moved:
            should_update_eta = True
        elif last_eta_update:
            seconds = (now - last_eta_update).total_seconds()
            if seconds > 10:
                should_update_eta = True
        else:
            should_update_eta = True

        if commande.gps and should_update_eta:

            try:
                lat_client, lng_client = map(float, commande.gps.split(","))

                url = f"http://router.project-osrm.org/route/v1/driving/{lng},{lat};{lng_client},{lat_client}?overview=false"

                res = requests.get(url, timeout=3)
                data_osrm = res.json()

                if "routes" in data_osrm and len(data_osrm["routes"]) > 0:

                    route = data_osrm["routes"][0]

                    new_eta = int(route["duration"] / 60)
                    dist_km = route["distance"] / 1000

                    # 🔥 LISSAGE ETA (ultra important)
                    if livraison.temps_restant:
                        old_eta = livraison.temps_restant
                        new_eta = int((old_eta * 0.7) + (new_eta * 0.3))

                    livraison.temps_restant = max(new_eta, 1)
                    livraison.last_eta_update = now

                    print(f"🧠 OSRM ETA: {new_eta} min | 📏 {dist_km:.2f} km")

            except Exception as e:
                print("❌ OSRM ERROR:", e)

        # =========================
        # 🔁 FALLBACK
        # =========================

        if livraison.temps_restant is None and commande.gps:
            try:
                lat_client, lng_client = map(float, commande.gps.split(","))

                dist_km = distance_km(lat, lng, lat_client, lng_client)

                eta = int((dist_km / vitesse) * 60)

                livraison.temps_restant = max(eta, 1)

                print(f"⚠️ FALLBACK ETA: {eta} min")

            except:
                livraison.temps_restant = None

        # =========================
        # 📍 ARRIVÉ ULTRA PRÉCISE
        # =========================

        if dist_km is not None and dist_km < 0.05:
            livraison.statut = "arrive"
            livraison.heure_arrivee = now
            commande.statut = "arrive"
            livraison.temps_restant = 0

        # =========================
        # 📞 TEL
        # =========================

        telephone = None
        if getattr(livreur, "telephone", None):
            telephone = livreur.telephone.replace("+", "").replace(" ", "")

        # =========================
        # 📡 SOCKET (🔥 UBER STYLE DATA)
        # =========================

        print("📡 EMIT ROOM:", commande.tracking_id)

        socketio.emit(
            "position_update",
            {
                "lat": lat,
                "lng": lng,
                "tracking": commande.tracking_id,
                "temps_restant": livraison.temps_restant,
                "statut": livraison.statut,
                "livreur_nom": getattr(livreur, "nom", "Livreur"),
                "livreur_tel": telephone,

                # 🔥 NOUVEAU (IMPORTANT FRONT)
                "vitesse": round(vitesse, 1),
                "distance_restante": round(dist_km, 2) if dist_km else None
            },
            room=commande.tracking_id
        )

    db.session.commit()

    return jsonify({
        "success": True,
        "temps_restant": livraison.temps_restant if livraison else None
    })

@app.route("/api/livreur/prendre", methods=["POST"])
@login_required
def prendre_commande():

    data = request.get_json()
    livraison_id = data.get("livraison_id")

    livraison = db.session.get(models.Livraison, livraison_id)

    if not livraison:
        return jsonify({"success": False, "error": "Livraison introuvable"}), 404

    # 🔐 Vérifier que c'est le bon livreur
    if livraison.livreur_id != current_user.id:
        return jsonify({"success": False, "error": "Accès refusé"}), 403

    # 🔥 RECUP COMMANDE
    commande = db.session.get(models.Commande, livraison.commande_id)

    # ✅ STATUT : PRIS (PAS en_route ici)
    livraison.statut = "pris"
    commande.statut = "pris"

    # 🔥 TEMPS INITIAL
    livraison.temps_restant = commande.temps_estime or 25

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Commande prise par le livreur"
    })

@app.route("/api/livreur/commandes", methods=["GET"])
@login_required
def commandes_livreur():

    livreur = current_user

    livraisons = models.Livraison.query.filter_by(livreur_id=livreur.id).all()

    data = []

    for l in livraisons:
        cmd = db.session.get(models.Commande, l.commande_id)

        if not cmd:
            continue

        data.append({
            "livraison_id": l.id,
            "tracking": cmd.tracking_id,
            "adresse": cmd.adresse,
            "gps": cmd.gps,

            # 🔥 STATUT LIVE
            "statut": l.statut,

            # 🔥 TEMPS RESTANT
            "temps_restant": l.temps_restant,

            # 🔥 BOUTON LIVRÉ ACTIVABLE
            "peut_livrer": True if l.statut in ["arrive", "en_route"] else False
        })

    return jsonify(data)

@app.route("/api/livreur/livrer", methods=["POST"])
@login_required
def livrer_commande():

    data = request.get_json()
    livraison_id = data.get("livraison_id")

    livraison = db.session.get(models.Livraison, livraison_id)

    if not livraison:
        return jsonify({"success": False}), 404

    if livraison.livreur_id != current_user.id:
        return jsonify({"success": False}), 403

    commande = db.session.get(models.Commande, livraison.commande_id)

    # 🔥 LIVREUR CONFIRME
    livraison.livreur_confirme = True
    livraison.statut = "livre"

    commande.statut = "livre"

    db.session.commit()

    return jsonify({"success": True})

# =========================
# LOGIN LIVREUR
# =========================
@app.route("/livreur/login", methods=["GET", "POST"])
def livreur_login():

    if current_user.is_authenticated and isinstance(current_user, models.Livreur):
        return redirect(url_for("livreur_dashboard"))

    if request.method == "POST":

        telephone = request.form.get("telephone")
        password = request.form.get("password")

        livreur = models.Livreur.query.filter_by(telephone=telephone).first()

        if livreur and check_password(password, livreur.password):
            login_user(livreur)
            return redirect(url_for("livreur_dashboard"))

        flash("Identifiants invalides ❌")

    return render_template("livreur_login.html")

@app.route("/livreur/dashboard")
@login_required
def livreur_dashboard():

    # 🔒 empêcher admin d'accéder ici
    if not isinstance(current_user, models.Livreur):
        logout_user()
        return redirect(url_for("livreur_login"))

    return render_template("livreur.html", livreur_id=current_user.id)


# =========================
# LOGOUT LIVREUR
# =========================
@app.route("/livreur/logout")
@login_required
def livreur_logout():
    logout_user()
    return redirect(url_for("livreur_login"))

# =========================
# 🚴 AJOUT LIVREUR
# =========================
@app.route("/admin/add_livreur", methods=["POST"])
@login_required
def add_livreur():

    nom = request.form.get("nom")
    telephone = request.form.get("telephone")
    password = request.form.get("password")

    # 🔐 sécuriser mot de passe
    password_hash = hash_password(password)

    livreur = models.Livreur(
        nom=nom,
        telephone=telephone,
        password=password_hash,
        disponible=True,
        note=5
    )

    db.session.add(livreur)
    db.session.commit()

    return redirect(url_for("admin_dashboard"))

# =========================
# ❌ DELETE LIVREUR
# =========================


@app.route("/admin/delete_livreur/<int:livreur_id>", methods=["POST"])
@login_required
def delete_livreur(livreur_id):

    livreur = db.session.get(models.Livreur, livreur_id)

    if not livreur:
        abort(404)

    # 🔥 SUPPRIMER LES LIVRAISONS LIÉES
    livraisons = models.Livraison.query.filter_by(livreur_id=livreur.id).all()

    for l in livraisons:
        db.session.delete(l)

    # 🔥 SUPPRIMER LE LIVREUR
    db.session.delete(livreur)
    db.session.commit()

    flash("Livreur supprimé avec succès 🚀")
    return redirect(url_for("admin_dashboard"))

# =========================
# DELETE COMMANDES (MULTIPLE)

@app.route("/admin/delete_commande/<int:id>", methods=["POST"])
@login_required
def delete_commande(id):

    try:
        commande = db.session.get(models.Commande, id)

        if not commande:
            flash("Commande introuvable ❌")
            return redirect(url_for("admin_dashboard"))

        # 🔥 1. supprimer livraison liée
        models.Livraison.query.filter_by(commande_id=id).delete()

        # 🔥 2. supprimer items
        models.CommandeItem.query.filter_by(commande_id=id).delete()

        # 🔥 3. supprimer avis
        models.Avis.query.filter_by(commande_id=id).delete()

        # 🔥 4. supprimer messages (lié par tracking)
        models.Message.query.filter_by(tracking=commande.tracking_id).delete()

        # 🔥 5. supprimer commande
        db.session.delete(commande)

        db.session.commit()

        flash("Commande supprimée avec succès ✅")

    except Exception as e:
        db.session.rollback()
        print("❌ ERREUR:", e)  # 🔥 IMPORTANT pour debug
        flash("Erreur lors de la suppression ❌")

    return redirect(url_for("admin_dashboard"))

# =========================
# 📍 GESTION DES ZONES
# =========================

@app.route("/admin/zones")
@login_required
def admin_zones():

    zones = models.Zone.query.all()

    return render_template("admin_zones.html", zones=zones)


@app.route("/admin/add_zone", methods=["POST"])
@login_required
def add_zone():

    nom = request.form.get("nom")
    prix_standard = request.form.get("prix_standard")
    prix_express = request.form.get("prix_express")

    if not nom:
        return redirect(url_for("admin_zones"))

    zone = models.Zone(
        nom=nom.strip(),
        prix_standard=int(prix_standard or 0),
        prix_express=int(prix_express or 0)
    )

    db.session.add(zone)
    db.session.commit()

    return redirect(url_for("admin_zones"))


@app.route("/admin/delete_zone/<int:zone_id>", methods=["POST"])
@login_required
def delete_zone(zone_id):

    zone = models.Zone.query.get_or_404(zone_id)

    db.session.delete(zone)
    db.session.commit()

    return redirect(url_for("admin_zones"))

# =========================
# 📦 PAGE SUIVI CLIENT
# =========================
@app.route("/suivi/<tracking>")
def suivi_commande(tracking):

    commande = models.Commande.query.filter_by(tracking_id=tracking).first()

    if not commande:
        return "Commande introuvable ❌"

    # 🔥 récupérer les items
    items = models.CommandeItem.query.filter_by(commande_id=commande.id).all()

    total_plats = sum(i.prix * i.quantite for i in items)

    # 🔥 injecter dans l'objet (comme tu fais déjà)
    commande.items = items
    commande.total_plats = total_plats

    return render_template("suivi.html", commande=commande)

# =========================
# 📱 GENERER QR CODE DESIGN WHÉKÉ (VIEW + AUTO DOWNLOAD)
# =========================
@app.route("/generate_qr")
@login_required
def generate_qr():

    import qrcode
    from PIL import Image, ImageDraw
    import io
    import base64

    # 🔗 Lien vers ton menu
    url = request.host_url

    # 🔲 QR HAUTE QUALITÉ
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=12,
        border=2
    )

    qr.add_data(url)
    qr.make(fit=True)

    # 🔥 Couleurs WHÉKÉ
    ORANGE = (255, 102, 0)
    WHITE = (255, 255, 255)

    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")

    # =========================
    # 🔶 FOND ORANGE
    # =========================
    size = qr_img.size[0] + 80
    bg = Image.new("RGBA", (size, size), ORANGE)

    pos_qr = ((size - qr_img.size[0]) // 2, (size - qr_img.size[1]) // 2)
    bg.paste(qr_img, pos_qr, qr_img)

    # =========================
    # 🔳 BORD ARRONDI
    # =========================
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size, size), radius=60, fill=255)
    bg.putalpha(mask)

    # =========================
    # 🖼️ LOGO AU CENTRE
    # =========================
    logo_path = os.path.join(app.static_folder, "logo.jpg")
    logo = Image.open(logo_path).convert("RGBA")

    qr_width = qr_img.size[0]
    logo_size = qr_width // 4
    logo = logo.resize((logo_size, logo_size))

    circle_size = logo_size + 20
    circle = Image.new("RGBA", (circle_size, circle_size), (255, 255, 255, 0))

    draw_circle = ImageDraw.Draw(circle)
    draw_circle.ellipse((0, 0, circle_size, circle_size), fill=WHITE)

    circle.paste(logo, ((circle_size - logo_size)//2, (circle_size - logo_size)//2), logo)

    center_pos = ((size - circle_size)//2, (size - circle_size)//2)
    bg.paste(circle, center_pos, circle)

    # =========================
    # 💾 CONVERTIR EN BASE64
    # =========================
    img_io = io.BytesIO()
    bg.save(img_io, 'PNG')
    img_io.seek(0)

    img_base64 = base64.b64encode(img_io.getvalue()).decode()

    # =========================
    # 📄 PAGE HTML + AUTO DOWNLOAD
    # =========================
    return f"""
    <html>
    <head>
        <title>QR WHÉKÉ FOOD</title>
    </head>
    <body style="text-align:center; font-family:sans-serif; background:#f4f6f9;">

        <h2>📱 QR Code WHÉKÉ FOOD</h2>

        <img id="qr" src="data:image/png;base64,{img_base64}" style="max-width:300px; border-radius:20px;"/>

        <p>Le téléchargement démarre automatiquement...</p>

        <script>
            const link = document.createElement('a');
            link.href = document.getElementById('qr').src;
            link.download = "qr_wheke_food.png";
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        </script>

    </body>
    </html>
    """

@app.route("/api/commande/update_gps", methods=["POST"])
def update_gps_client():

    data = request.get_json()
    tracking = data.get("tracking")
    gps = data.get("gps")

    commande = models.Commande.query.filter_by(tracking_id=tracking).first()

    if not commande:
        return jsonify({"success": False})

    commande.gps = gps
    db.session.commit()

    return jsonify({"success": True})

# =========================
# 💬 CHAT CLIENT ↔ LIVREUR
# =========================

@socketio.on("send_message")
def handle_message(data):
    try:
        tracking = data.get("tracking")
        message = data.get("message")
        sender = data.get("sender")

        if not tracking or not message or not sender:
            return

        # 💾 SAUVEGARDE EN DB
        msg = models.Message(
            tracking=tracking,
            message=message,
            sender=sender
        )
        db.session.add(msg)
        db.session.commit()

        # 📡 ENVOI TEMPS RÉEL
        socketio.emit("receive_message", {
            "tracking": tracking,
            "message": message,
            "sender": sender
        }, room=tracking)

    except Exception as e:
        print("❌ Erreur socket message:", e)        

@socketio.on("join_room")
def handle_join_room(data):
    tracking = data.get("tracking")

    if tracking:
        join_room(tracking)
        print(f"🚪 Livreur rejoint la room : {tracking}")   

@app.route("/api/messages/<tracking>")
def get_messages(tracking):

    messages = models.Message.query.filter_by(tracking=tracking)\
        .order_by(models.Message.date.asc()).all()

    return jsonify([
        {
            "message": m.message,
            "sender": m.sender
        } for m in messages
    ])

@app.route("/api/livreur/delete_messages", methods=["POST"])
@login_required
def delete_messages_livreur():

    data = request.get_json()
    livraison_id = data.get("livraison_id")

    livraison = db.session.get(models.Livraison, livraison_id)

    if not livraison:
        return jsonify({"success": False}), 404

    # 🔐 sécurité : vérifier que c’est le BON livreur
    if livraison.livreur_id != current_user.id:
        return jsonify({"success": False}), 403

    commande = db.session.get(models.Commande, livraison.commande_id)

    if not commande:
        return jsonify({"success": False}), 404

    # ❗ autoriser suppression seulement si livré
    if commande.statut != "livre":
        return jsonify({
            "success": False,
            "error": "Commande non livrée"
        }), 400

    # 🔥 suppression des messages
    models.Message.query.filter_by(tracking=commande.tracking_id).delete()

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Messages supprimés"
    })


# =========================
# 🔒 VERIFICATION SUPER ADMIN
# =========================
def super_admin_required():

    # 🔒 doit être connecté
    if not current_user.is_authenticated:
        abort(403)

    # 🔒 doit être un admin (évite erreur livreur)
    if not hasattr(current_user, "role"):
        abort(403)

    # 🔒 doit être super admin
    if current_user.role != "super_admin":
        abort(403)
# =========================
# 📄 PAGE GESTION ADMINS
# =========================
@app.route("/admin/admins")
@login_required
def admin_list():

    super_admin_required()

    admins = models.Admin.query.all()

    return render_template("admin_admins.html", admins=admins)

# =========================
# ➕ AJOUT ADMIN
# =========================
@app.route("/admin/add_admin", methods=["POST"])
@login_required
def add_admin():

    super_admin_required()

    username = request.form.get("username")
    password = request.form.get("password")

    if not username or not password:
        flash("Champs manquants ❌")
        return redirect(url_for("admin_list"))

    existing = models.Admin.query.filter_by(username=username).first()
    if existing:
        flash("Admin déjà existant ❌")
        return redirect(url_for("admin_list"))

    new_admin = models.Admin(
        username=username,
        password=hash_password(password),
        role="admin"
    )

    db.session.add(new_admin)
    db.session.commit()

    flash("Admin ajouté ✅")
    return redirect(url_for("admin_list"))

# =========================
# ❌ DELETE ADMIN
# =========================
@app.route("/admin/delete_admin/<int:admin_id>", methods=["POST"])
@login_required
def delete_admin(admin_id):

    super_admin_required()

    admin = models.Admin.query.get_or_404(admin_id)

    if admin.role == "super_admin":
        flash("Impossible de supprimer le super admin ❌")
        return redirect(url_for("admin_list"))

    db.session.delete(admin)
    db.session.commit()

    flash("Admin supprimé 🚀")
    return redirect(url_for("admin_list"))