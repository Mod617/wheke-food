// ==========================
// PANIER (PRO)
// ==========================

let panier = JSON.parse(localStorage.getItem("panier")) || [];
let premierAjout = true;
let autoCloseTimer = null;
let lastAddTime = 0;

function sauvegarderPanier() {
    localStorage.setItem("panier", JSON.stringify(panier));
}

// ==========================
// 🔴 BADGE ANIMATION
// ==========================

function pulsePanier() {
    let btn = document.getElementById("panier_btn");
    if (!btn) return;

    btn.style.transition = "transform 0.3s";
    btn.style.transform = "scale(1.2)";

    setTimeout(() => {
        btn.style.transform = "scale(1)";
    }, 300);
}

// ==========================
// 🔔 NOTIFICATION
// ==========================

function notification(msg) {
    let notif = document.createElement("div");
    notif.innerText = msg;

    notif.style.position = "fixed";
    notif.style.bottom = "20px";
    notif.style.left = "50%";
    notif.style.transform = "translateX(-50%)";
    notif.style.background = "#111";
    notif.style.color = "white";
    notif.style.padding = "12px 20px";
    notif.style.borderRadius = "10px";
    notif.style.zIndex = "9999";
    notif.style.opacity = "0";
    notif.style.transition = "all 0.4s";

    document.body.appendChild(notif);

    setTimeout(() => {
        notif.style.opacity = "1";
        notif.style.bottom = "40px";
    }, 10);

    setTimeout(() => {
        notif.style.opacity = "0";
        notif.remove();
    }, 2000);
}

// ==========================
// 📱 PANIER SLIDE
// ==========================
function ouvrirPanier() {
    let p = document.getElementById("panier_popup");
    let overlay = document.getElementById("panier_overlay");

    if (!p) return;

    p.style.display = "flex";

    if (overlay) overlay.classList.add("active");

    if (window.innerWidth <= 768) {

        p.style.transform = "translateY(100%)";

        setTimeout(() => {
            p.style.transition = "transform 0.4s ease";
            p.style.transform = "translateY(0)";
        }, 10);

    } else {

        p.style.transform = "translateX(100%)";

        setTimeout(() => {
            p.style.transition = "transform 0.4s ease";
            p.style.transform = "translateX(0)";
        }, 10);
    }
}

function fermerPanier() {
    let p = document.getElementById("panier_popup");
    let overlay = document.getElementById("panier_overlay");

    if (!p) return;

    if (window.innerWidth <= 768) {
        p.style.transform = "translateY(100%)";
    } else {
        p.style.transform = "translateX(100%)";
    }

    if (overlay) overlay.classList.remove("active");

    setTimeout(() => {
        p.style.display = "none";
    }, 300);
}

function ouvrirPanierAuto() {
    let panier = document.getElementById("panier_popup");

    if (panier && !panier.classList.contains("open")) {
        panier.classList.add("open");
        document.body.classList.add("panier-open");
    }
}

// ==========================
// QUANTITE PRODUIT
// ==========================

function plus(id) {
    let q = document.getElementById("q" + id);
    if (!q) return;

    let val = parseInt(q.value) || 1;
    q.value = val + 1;
}

function moins(id) {
    let q = document.getElementById("q" + id);
    if (!q) return;

    let val = parseInt(q.value) || 1;
    if (val > 1) q.value = val - 1;
}

// ==========================
// 🔥 ANIMATION FLUIDE
// ==========================

function animationPanier(event) {
    let card = event.target.closest(".plat");
    if (!card) return;

    let img = card.querySelector("img");
    let panierBtn = document.getElementById("panier_btn");

    if (!img || !panierBtn) return;

    let clone = img.cloneNode(true);
    let rect = img.getBoundingClientRect();
    let panierRect = panierBtn.getBoundingClientRect();

    clone.style.position = "fixed";
    clone.style.left = rect.left + "px";
    clone.style.top = rect.top + "px";
    clone.style.width = rect.width + "px";
    clone.style.height = rect.height + "px";
    clone.style.transition = "all 0.8s cubic-bezier(0.4,0,0.2,1)";
    clone.style.zIndex = "999";

    document.body.appendChild(clone);

    setTimeout(() => {
        clone.style.left = panierRect.left + "px";
        clone.style.top = panierRect.top + "px";
        clone.style.width = "30px";
        clone.style.height = "30px";
        clone.style.opacity = "0.3";
    }, 50);

    setTimeout(() => clone.remove(), 800);
}

// ==========================
// AJOUT PANIER
// ==========================

function ajouterPanier(event, id, nom, prix, promo = 0) {

    // 🚫 Anti spam clic rapide (UX propre)
    let now = Date.now();
    if (now - lastAddTime < 300) return;
    lastAddTime = now;

    // 🔥 Animation produit → panier
    animationPanier(event);

    let card = event.target.closest(".plat");

    let img = "";
    if (card) {
        let imageElement = card.querySelector("img");
        if (imageElement && imageElement.src && imageElement.src !== "undefined") {
            img = imageElement.src;
        }
    }

    let qInput = document.getElementById("q" + id);
    let q = parseInt(qInput?.value) || 1;

    prix = parseFloat(prix);
    if (isNaN(prix) || prix <= 0) {
        alert("Erreur prix");
        return;
    }

    let existing = panier.find(item => item.id === id);

    if (existing) {
        existing.quantite += q;
    } else {
        panier.push({
            id: id,
            nom: nom,
            prix: prix,
            quantite: q,
            image: img
        });
    }

    sauvegarderPanier();
    afficherPanier();

    // ==========================
    // 🛒 UPDATE BOUTON PANIER (LIVE)
    // ==========================
    let count = 0;
    let total = 0;

    panier.forEach(item => {
        count += item.quantite;
        total += item.prix * item.quantite;
    });

    let btn = document.getElementById("panier_btn");

    if (btn) {
        btn.innerHTML = `🛒 (${count}) • ${total} FCFA`;
    }

    // ==========================
    // 🎯 OUVERTURE SMART MOBILE
    // ==========================
    if (window.innerWidth <= 768) {

        // 🟢 PREMIER AJOUT → ouverture auto
        if (premierAjout) {

            ouvrirPanier();

            autoCloseTimer = setTimeout(() => {
                fermerPanier();
            }, 5000);

            premierAjout = false;

        } else {

            // 🔁 AJOUTS SUIVANTS → juste vibration bouton
            pulsePanier();

            // 🔄 Reset timer si panier déjà ouvert
            if (autoCloseTimer) {
                clearTimeout(autoCloseTimer);

                autoCloseTimer = setTimeout(() => {
                    fermerPanier();
                }, 3000);
            }
        }
    }

    // 🔥 effet bounce bouton
    pulsePanier();

    // ==========================
    // 🔔 NOTIF
    // ==========================
    notification("✔️ Ajouté au panier");

    // ==========================
    // 🎁 PROMO ANIMATION
    // ==========================
    if (promo > 0) {

        let gift = document.getElementById("gift_animation");

        if (gift) {

            gift.classList.add("active");

            setTimeout(() => {
                gift.classList.add("shake");
            }, 200);

            setTimeout(() => {
                gift.classList.remove("shake");
                gift.classList.add("open");
            }, 800);

            setTimeout(() => {
                gift.classList.add("boom");
                gift.classList.add("show-text");

                confetti({
                    particleCount: 300,
                    spread: 180,
                    origin: { y: 0.6 }
                });

            }, 1000);

            setTimeout(() => {
                gift.classList.remove("active","open","boom","show-text");
            }, 3000);
        }
    }
}
// ==========================
// 🔥 GESTION INTELLIGENTE DES METS (AJOUT)
// ==========================

function gererDisponibiliteMets() {
    let plats = document.querySelectorAll(".plat");
    let aujourdHui = new Date();

    plats.forEach(plat => {
        let dateStr = plat.getAttribute("data-date");
        if (!dateStr) return;

        let datePlat = new Date(dateStr);

        // ❌ Supprimer si expiré
        if (datePlat < aujourdHui.setHours(0,0,0,0)) {
            plat.remove();
            return;
        }

        // 📅 Calcul jours restants
        let diff = Math.ceil((datePlat - new Date()) / (1000 * 60 * 60 * 24));

        let label = plat.querySelector(".dispo-label");
        if (!label) {
            label = document.createElement("div");
            label.className = "dispo-label";
            label.style.fontSize = "12px";
            label.style.marginTop = "5px";
            label.style.color = "#ff9800";
            plat.appendChild(label);
        }

        if (diff <= 0) {
            label.innerText = "✅ Disponible aujourd’hui";
        } else if (diff === 1) {
            label.innerText = "🕒 Disponible demain";
        } else {
            label.innerText = "📅 Dans " + diff + " jours";
        }
    });

    // 🔥 TRI AUTOMATIQUE
    let container = document.querySelector(".plats_container");
    if (!container) return;

    let platsArray = Array.from(container.querySelectorAll(".plat"));

    platsArray.sort((a, b) => {
        let da = new Date(a.getAttribute("data-date"));
        let db = new Date(b.getAttribute("data-date"));
        return da - db;
    });

    platsArray.forEach(p => container.appendChild(p));
}

// ==========================
// MODIFIER QUANTITE
// ==========================

function augmenter(index) {
    panier[index].quantite++;
    sauvegarderPanier();
    afficherPanier();
}

function diminuer(index) {
    if (panier[index].quantite > 1) {
        panier[index].quantite--;
    }
    sauvegarderPanier();
    afficherPanier();
}

// ==========================
// SUPPRIMER
// ==========================

function supprimer(index) {
    panier.splice(index, 1);
    sauvegarderPanier();
    afficherPanier();
}

// ==========================
// AFFICHAGE PANIER
// ==========================

function afficherPanier() {
    let div = document.getElementById("panier_items");
    if (!div) return;

    div.innerHTML = "";

    let total = 0;
    let count = 0;

    panier.forEach((item, index) => {
        let prixTotal = item.prix * item.quantite;

        total += prixTotal;
        count += item.quantite;

        div.innerHTML += `
        <div style="display:flex;gap:12px;padding:12px;margin-bottom:12px;border-radius:12px;background:#fff;box-shadow:0 2px 8px rgba(0,0,0,0.08);align-items:center;">
            
            <img src="${item.image || ''}" style="width:65px;height:65px;object-fit:cover;border-radius:10px;">

            <div style="flex:1;">
                
                <div style="font-weight:bold;margin-bottom:4px;">
                    ${item.nom}
                </div>

                <div style="font-size:13px;color:#666;">
                    ${item.prix} FCFA
                </div>

                <!-- 🔥 QUANTITÉ PROPRE -->
                <div style="margin-top:8px;display:flex;align-items:center;gap:10px;">
                    
                    <button onclick="diminuer(${index})"
                        style="width:30px;height:30px;background:#ff3b3b;color:white;border:none;border-radius:8px;font-weight:bold;cursor:pointer;">
                        -
                    </button>

                    <div style="
                        min-width:35px;
                        text-align:center;
                        font-weight:bold;
                        font-size:16px;
                        background:#f2f2f2;
                        padding:5px 10px;
                        border-radius:8px;
                        color:#000 !important;
                    ">
                        ${item.quantite}
                    </div>

                    <button onclick="augmenter(${index})"
                        style="width:30px;height:30px;background:#00c853;color:white;border:none;border-radius:8px;font-weight:bold;cursor:pointer;">
                        +
                    </button>

                </div>

                <!-- 💰 PRIX TOTAL -->
                <div style="margin-top:6px;color:#28a745;font-weight:bold;">
                    ${prixTotal} FCFA
                </div>

                <!-- 🗑️ SUPPRIMER -->
                <button onclick="supprimer(${index})"
                    style="margin-top:8px;background:#111;color:white;border:none;padding:6px;border-radius:8px;width:100%;cursor:pointer;">
                    Supprimer
                </button>

            </div>

        </div>
        `;
    });

    let countDiv = document.getElementById("panier_count");
    if (countDiv) countDiv.innerText = count;

    let totalDiv = document.getElementById("panier_total");
    if (totalDiv) totalDiv.innerText = total;
}

// ==========================
// ENVOI COMMANDE
// ==========================

function envoyerCommande_old_DISABLED() {
    if (panier.length === 0) {
        alert("Votre panier est vide");
        return;
    }

    let telephone = prompt("📞 Entrez votre numéro :");
    if (!telephone) return;

    let adresse = prompt("📍 Entrez votre quartier :");
    if (!adresse) return;

    // 🔥 NOUVEAU : type de livraison
    let livraison = prompt("🚚 Type de livraison (livraison / retrait) :");
    if (!livraison) {
        alert("Choisir un type de livraison");
        return;
    }

    let data = {
        telephone: telephone,
        adresse: adresse,
        gps: "", // on garde ton fonctionnement
        livraison: livraison, // ✅ AJOUT CRITIQUE
        panier: panier.map(item => ({
            id: item.id,
            qte: item.quantite
        }))
    };

    fetch("/commander", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(data)
    })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                alert("✅ Commande envoyée ! Code : " + data.tracking);

                panier = [];
                localStorage.removeItem("panier");

                afficherPanier();
                fermerPanier();
            } else {
                alert("❌ " + (data.message || "Erreur commande"));
            }
        })
        .catch(() => {
            alert("❌ Erreur serveur");
        });
}

function envoyerCommande() {
    if (panier.length === 0) {
        alert("Votre panier est vide");
        return;
    }

    let telephone = prompt("📞 Entrez votre numéro :");
    if (!telephone) return;

    let adresse = prompt("📍 Entrez votre quartier :");
    if (!adresse) return;

    let livraison = prompt("🚚 Type de livraison (livraison / retrait) :");
    if (!livraison) {
        alert("Choisir un type de livraison");
        return;
    }

    let data = {
        telephone: telephone,
        adresse: adresse,
        gps: "",
        livraison: livraison,
        panier: panier.map(item => ({
            id: item.id,
            qte: item.quantite
        }))
    };

    fetch("/commander", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(data)
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {

            // 🔥 REDIRECTION AUTOMATIQUE
            window.location.href = "/suivi/" + data.tracking;

        } else {
            alert("❌ " + (data.message || "Erreur commande"));
        }
    })
    .catch(() => {
        alert("❌ Erreur serveur");
    });
}

// ==========================
// 📦 COMMANDES UTILISATEUR
// ==========================

function voirCommandes(){
    let commandes = JSON.parse(localStorage.getItem("commandes") || "[]");
    if(commandes.length === 0){
        alert("Aucune commande trouvée ❌");
        return;
    }

    let html = "📦 Vos commandes :\n\n";
    commandes.forEach(c=>{
        html += "➡ " + c.tracking + " ("+c.date+")\n";
    });

    html += "\nCliquez OK pour ouvrir la dernière";

    if(confirm(html)){
        let last = commandes[commandes.length - 1];
        window.location.href = "/suivi/" + last.tracking;
    }
}

// ==========================
// 🔔 NOTIF SIMPLE
// ==========================

function showNotif() {
    let n = document.getElementById("notif");
    if(n) {
        n.classList.add("show");
        setTimeout(() => { n.classList.remove("show"); }, 2000);
    }
}

// ==========================
// NAVIGATION
// ==========================

function scrollToSection(id) { 
    const el = document.getElementById(id);
    if(el) el.scrollIntoView({behavior: "smooth"}); 
}

function scrollToTop() { 
    window.scrollTo({top: 0, behavior: 'smooth'}); 
}

// ==========================
// SCROLL GLOBAL
// ==========================

window.onscroll = function() {

    let btnTop = document.getElementById("backToTop");

    if (document.body.scrollTop > 300 || document.documentElement.scrollTop > 300) {
        if(btnTop) btnTop.style.display = "block";
    } else {
        if(btnTop) btnTop.style.display = "none";
    }

    const header = document.querySelector("header");
    if (header) {
        if (window.scrollY > 50) {
            header.classList.add("scrolled");
        } else {
            header.classList.remove("scrolled");
        }
    }
};

// Exécuter au chargement de la page
document.addEventListener("DOMContentLoaded", () => {
    afficherPanier();
});