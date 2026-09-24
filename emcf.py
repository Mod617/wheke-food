# emcf.py
"""
Client pour l'API e-MCF (SYGMEF) de la DGI Bénin.
⚠️ Endpoints et enums basés sur des SDK tiers non-officiels — à confirmer
avec la documentation reçue de la DGI avant mise en production.
"""

import json
import requests
from datetime import datetime
from flask import current_app as app

from extensions import db
import models


# =========================
# BAS NIVEAU : APPELS API
# =========================

def _headers():
    return {
        "Authorization": f"Bearer {app.config['EMCF_TOKEN']}",
        "Content-Type": "application/json"
    }

def _invoice_url(path=""):
    return f"{app.config['EMCF_BASE_URL']}/invoice{path}"

def emcf_status():
    r = requests.get(_invoice_url("/"), headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()

def emcf_creer_facture(payload):
    r = requests.post(_invoice_url("/"), json=payload, headers=_headers(), timeout=15)
    data = r.json()
    if r.status_code >= 400 or data.get("errorCode"):
        raise RuntimeError(data.get("errorDesc") or f"Erreur e-MCF (HTTP {r.status_code})")
    return data

def emcf_finaliser_facture(uid, action="confirm"):
    r = requests.put(_invoice_url(f"/{uid}/{action}"), headers=_headers(), timeout=15)
    data = r.json()
    if r.status_code >= 400 or data.get("errorCode"):
        raise RuntimeError(data.get("errorDesc") or f"Erreur e-MCF (HTTP {r.status_code})")
    return data


# =========================
# CONSTRUCTION DU PAYLOAD
# =========================

def _mode_paiement_emcf(mode_paiement):
    mapping = {
        "mtn": "MOBILEMONEY",
        "moov": "MOBILEMONEY",
        "mobile_money": "MOBILEMONEY",
        "card": "CARTEBANCAIRE",
        "carte": "CARTEBANCAIRE",
    }
    return mapping.get((mode_paiement or "").lower(), "AUTRE")


def construire_payload_facture(commande, items):
    # ⚠️ TaxGroup unique pour tout (A à F) — confirme la bonne lettre pour la
    # restauration/régime TPS auprès de la DGI. Valeur lue depuis EMCF_TAX_GROUP.
    tax_group = app.config["EMCF_TAX_GROUP"]

    lignes = []
    for item in items:
        lignes.append({
            "name": (item.met_nom or "Article")[:200],
            "price": float(item.prix),
            "quantity": int(item.quantite),
            "taxGroup": tax_group
        })

    if commande.prix_livraison:
        lignes.append({
            "name": "Frais de livraison",
            "price": float(commande.prix_livraison),
            "quantity": 1,
            "taxGroup": tax_group
        })

    payload = {
        "ifu": app.config["EMCF_IFU"],
        "type": "FV",
        "items": lignes,
        "operator": {"name": "Whèkè Food"},
        "payment": [{
            "name": _mode_paiement_emcf(commande.mode_paiement),
            "amount": int(commande.total)
        }],
        "reference": commande.tracking_id
    }

    if commande.client_ifu or commande.client_raison_sociale:
        payload["client"] = {
            "ifu": commande.client_ifu,
            "name": commande.client_raison_sociale,
            "contact": commande.telephone
        }

    return payload


# =========================
# ORCHESTRATION : CRÉER + CONFIRMER LA FACTURE D'UNE COMMANDE
# =========================

def emettre_facture_pour_commande(commande_id):
    """
    À appeler juste après confirmation du paiement d'une commande.
    Ne lève jamais d'exception : le paiement ne doit jamais être bloqué par
    un souci de facturation. Toute erreur est stockée sur la Facture (retry possible).
    """
    if not app.config.get("EMCF_ENABLED"):
        return None

    commande = db.session.get(models.Commande, commande_id)
    if not commande:
        return None

    facture = models.Facture.query.filter_by(
        commande_id=commande.id, type_facture="FV"
    ).order_by(models.Facture.id.desc()).first()

    if facture and facture.statut == "confirmee":
        return facture

    items = models.CommandeItem.query.filter_by(commande_id=commande.id).all()

    if not facture:
        facture = models.Facture(
            commande_id=commande.id,
            type_facture="FV",
            statut="en_attente",
            client_ifu=commande.client_ifu,
            client_nom=commande.client_raison_sociale,
            total=commande.total,
            mode_paiement=commande.mode_paiement
        )
        db.session.add(facture)
        db.session.commit()

    try:
        if not facture.uid:
            payload = construire_payload_facture(commande, items)
            facture.lignes_json = json.dumps(payload["items"], ensure_ascii=False)

            reponse_creation = emcf_creer_facture(payload)
            facture.uid = reponse_creation.get("uid")
            facture.total = reponse_creation.get("total") or facture.total
            facture.statut = "demandee"
            db.session.commit()

        reponse_confirmation = emcf_finaliser_facture(facture.uid, "confirm")

        facture.statut = "confirmee"
        facture.code_mecef = reponse_confirmation.get("codeMECeFDGI")
        facture.nim = reponse_confirmation.get("nim")
        facture.qr_code = reponse_confirmation.get("qrCode")
        facture.compteurs = reponse_confirmation.get("counters")
        facture.date_mecef = reponse_confirmation.get("dateTime")
        facture.reponse_brute = json.dumps(reponse_confirmation, ensure_ascii=False)
        facture.date_confirmation = datetime.utcnow()
        db.session.commit()

        return facture

    except Exception as e:
        db.session.rollback()
        facture = db.session.get(models.Facture, facture.id)
        facture.tentatives = (facture.tentatives or 0) + 1
        facture.derniere_erreur = str(e)[:2000]
        db.session.commit()
        print(f"⚠️ Erreur émission facture e-MCF (commande {commande.tracking_id}) : {e}")
        return None
