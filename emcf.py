# emcf.py
"""
Client pour l'API e-MCF (SYGMEF) de la DGI Bénin — v1.0, doc officielle DGI (15/01/2021).
"""

import json
import requests
from datetime import datetime
from flask import current_app as app

from extensions import db
import models


# =========================
# BAS NIVEAU : APPELS API — FACTURATION
# =========================

def _headers():
    return {
        "Authorization": f"Bearer {app.config['EMCF_TOKEN']}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

def _invoice_url(path=""):
    return f"{app.config['EMCF_BASE_URL']}/invoice{path}"

def _info_url(path=""):
    return f"{app.config['EMCF_BASE_URL']}/info{path}"

def emcf_status():
    """GET /invoice/ — statut de l'API, validité du jeton, factures en attente."""
    r = requests.get(_invoice_url("/"), headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()

def emcf_creer_facture(payload):
    """POST /invoice/ — soumet la facture, renvoie uid + totaux calculés par l'e-MCF."""
    r = requests.post(_invoice_url("/"), json=payload, headers=_headers(), timeout=15)
    data = r.json()
    if r.status_code >= 400 or data.get("errorCode"):
        raise RuntimeError(data.get("errorDesc") or f"Erreur e-MCF (HTTP {r.status_code})")
    return data

def emcf_finaliser_facture(uid, action="confirm"):
    """
    PUT /invoice/{uid}/{action} — action = 'confirm' ou 'annuler'.
    ⚠️ La doc officielle indique "Method: POST" dans le texte, mais l'exemple concret
    montre bien "PUT /api/invoice/{uid}/confirm". On suit l'exemple (PUT) ; si l'API
    répond 405, tenter POST comme repli.
    """
    r = requests.put(_invoice_url(f"/{uid}/{action}"), headers=_headers(), timeout=15)
    data = r.json()
    if r.status_code >= 400 or data.get("errorCode"):
        raise RuntimeError(data.get("errorDesc") or f"Erreur e-MCF (HTTP {r.status_code})")
    return data

def emcf_details_facture(uid):
    """GET /invoice/{uid} — relit une facture en attente (avant finalisation)."""
    r = requests.get(_invoice_url(f"/{uid}"), headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()


# =========================
# BAS NIVEAU : APPELS API — INFORMATION (diagnostic)
# =========================

def emcf_info_status():
    """GET /info/status — état de tous les e-MCF du compte."""
    r = requests.get(_info_url("/status"), headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()

def emcf_tax_groups():
    """GET /info/taxGroups — valeurs réelles des groupes A à F (en %). À vérifier avant de choisir EMCF_TAX_GROUP."""
    r = requests.get(_info_url("/taxGroups"), headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()

def emcf_payment_types():
    r = requests.get(_info_url("/paymentTypes"), headers=_headers(), timeout=15)
    r.raise_for_status()
    return r.json()


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
    # ⚠️ Groupe de taxation : à confirmer avec emcf_tax_groups() et ton comptable —
    # probablement un groupe à 0% (A/C/E/F) si tu es en régime TPS (forfait, hors TVA).
    tax_group = app.config["EMCF_TAX_GROUP"]

    lignes = []
    for item in items:
        lignes.append({
            "name": (item.met_nom or "Article")[:200],
            "price": int(round(item.prix)),      # ⬅️ integer, pas float
            "quantity": item.quantite,
            "taxGroup": tax_group
        })

    if commande.prix_livraison:
        lignes.append({
            "name": "Frais de livraison",
            "price": int(round(commande.prix_livraison)),
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
            "amount": int(round(commande.total))
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
