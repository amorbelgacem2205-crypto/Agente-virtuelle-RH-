"""
Outil : facturation suisse — créer factures, lister, relancer impayés.

TVA suisse 2024+ :
  - Taux normal : 8.1 %
  - Taux réduit (alimentation, livres) : 2.6 %
  - Taux spécial (hôtellerie) : 3.8 %
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path

DONNEES_DIR = Path(__file__).parent.parent / "donnees"
FACTURES_CSV = DONNEES_DIR / "factures.csv"
CLIENTS_CSV = DONNEES_DIR / "clients.csv"
FACTURES_GEN_DIR = Path(__file__).parent.parent / "factures_generees"
FACTURES_GEN_DIR.mkdir(exist_ok=True)

# Coordonnées de l'entreprise émettrice
ENTREPRISE = {
    "nom": "ACME Suisse SA",
    "adresse": "Rue de l'Innovation 12",
    "npa": "1003",
    "ville": "Lausanne",
    "pays": "Suisse",
    "no_tva": "CHE-987.654.321",
    "iban": "CH93 0076 2011 6238 5295 7",
    "bic": "POFICHBEXXX",
    "email": "facturation@acme.ch",
    "telephone": "+41 21 555 00 00",
}

TAUX_TVA = {
    "normal": 8.1,
    "reduit": 2.6,
    "hotellerie": 3.8,
    "exonere": 0.0,
}


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _charger_factures() -> list[dict]:
    if not FACTURES_CSV.exists():
        return []
    with open(FACTURES_CSV, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _charger_clients() -> list[dict]:
    if not CLIENTS_CSV.exists():
        return []
    with open(CLIENTS_CSV, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _trouver_client(id_client: str) -> dict | None:
    for c in _charger_clients():
        if c["id_client"].upper() == id_client.upper():
            return c
    return None


def _trouver_facture(numero: str) -> dict | None:
    for f in _charger_factures():
        if f["numero"].upper() == numero.upper():
            return f
    return None


def _fmt(x: float) -> str:
    return f"{x:,.2f}".replace(",", "'")


def _ecrire_factures(factures: list[dict]):
    if not factures:
        return
    fieldnames = [
        "numero", "id_client", "date_emission", "date_echeance",
        "montant_ht", "taux_tva", "montant_tva", "montant_ttc",
        "description", "statut", "date_paiement",
    ]
    with open(FACTURES_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(factures)


# ----------------------------------------------------------------------
# CRUD CLIENTS
# ----------------------------------------------------------------------
def _ecrire_clients(clients: list[dict]):
    fieldnames = [
        "id_client", "nom", "contact", "email", "telephone",
        "adresse", "npa", "ville", "pays", "no_tva",
    ]
    with open(CLIENTS_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(clients)


def creer_client(
    nom: str,
    email: str,
    contact: str = "",
    telephone: str = "",
    adresse: str = "",
    npa: str = "",
    ville: str = "",
    pays: str = "CH",
    no_tva: str = "",
) -> str:
    """Ajoute un nouveau client à la base."""
    nom = (nom or "").strip()
    email = (email or "").strip()
    if not nom:
        return "❌ Le nom de l'entreprise est obligatoire."
    if not email or "@" not in email:
        return "❌ Une adresse email valide est obligatoire."

    clients = _charger_clients()

    # Vérifier doublons (par email ou nom)
    for c in clients:
        if c["email"].lower() == email.lower():
            return f"❌ Un client avec l'email {email} existe déjà : {c['id_client']} — {c['nom']}."
        if c["nom"].lower() == nom.lower():
            return f"⚠️ Un client avec le nom '{nom}' existe déjà : {c['id_client']}. Utilise modifier_client pour le mettre à jour."

    # ID auto : CLI001, CLI002, …
    nums = []
    for c in clients:
        try:
            nums.append(int(c["id_client"].replace("CLI", "")))
        except (ValueError, AttributeError):
            pass
    prochain = (max(nums) if nums else 0) + 1
    id_client = f"CLI{prochain:03d}"

    nouveau = {
        "id_client": id_client,
        "nom": nom,
        "contact": contact.strip() or "—",
        "email": email,
        "telephone": telephone.strip(),
        "adresse": adresse.strip(),
        "npa": npa.strip(),
        "ville": ville.strip(),
        "pays": (pays or "CH").upper().strip(),
        "no_tva": no_tva.strip(),
    }
    clients.append(nouveau)
    _ecrire_clients(clients)

    return (
        f"✅ Client {id_client} créé : {nom}\n"
        f"   Contact   : {contact or '—'}\n"
        f"   Email     : {email}\n"
        f"   Téléphone : {telephone or '—'}\n"
        f"   Adresse   : {adresse or '—'}, {npa or ''} {ville or ''} ({pays})\n"
        f"   N° TVA    : {no_tva or '—'}\n\n"
        f"💡 Tu peux maintenant lui créer une facture avec :\n"
        f'   « Crée une facture pour {id_client} de XXX CHF, description "..." »'
    )


def lister_clients() -> str:
    """Liste tous les clients enregistrés."""
    clients = _charger_clients()
    if not clients:
        return "Aucun client enregistré. Utilise creer_client pour en ajouter."
    out = [f"=== {len(clients)} client(s) enregistré(s) ===\n"]
    for c in clients:
        out.append(
            f"• {c['id_client']} — {c['nom']}\n"
            f"   Contact  : {c['contact']}  |  Email : {c['email']}\n"
            f"   Adresse  : {c['adresse']}, {c['npa']} {c['ville']} ({c['pays']})\n"
            f"   N° TVA   : {c.get('no_tva') or '—'}"
        )
    return "\n\n".join(out)


def modifier_client(id_client: str, champ: str, nouvelle_valeur: str) -> str:
    """
    Modifie un champ d'un client existant.

    Champs autorisés : nom, contact, email, telephone, adresse, npa, ville, pays, no_tva
    """
    champs_ok = {"nom", "contact", "email", "telephone", "adresse", "npa", "ville", "pays", "no_tva"}
    if champ not in champs_ok:
        return f"❌ Champ inconnu : {champ}. Champs valides : {sorted(champs_ok)}"
    clients = _charger_clients()
    for c in clients:
        if c["id_client"].upper() == id_client.upper():
            ancienne = c[champ]
            c[champ] = nouvelle_valeur
            _ecrire_clients(clients)
            return (
                f"✅ Client {id_client} mis à jour.\n"
                f"   {champ} : {ancienne or '—'} → {nouvelle_valeur}"
            )
    return f"❌ Client introuvable : {id_client}"


def supprimer_client(id_client: str) -> str:
    """Supprime un client (refuse si des factures existent pour ce client)."""
    clients = _charger_clients()
    factures = _charger_factures()
    if any(f["id_client"].upper() == id_client.upper() for f in factures):
        return (
            f"❌ Impossible de supprimer {id_client} : des factures existent pour ce client. "
            f"Pour des raisons légales (conservation 10 ans en Suisse), il faut conserver l'historique."
        )
    nouveau = [c for c in clients if c["id_client"].upper() != id_client.upper()]
    if len(nouveau) == len(clients):
        return f"❌ Client introuvable : {id_client}"
    _ecrire_clients(nouveau)
    return f"✅ Client {id_client} supprimé."


# ----------------------------------------------------------------------
# Outil 1 — Créer une facture
# ----------------------------------------------------------------------
def creer_facture(
    id_client: str,
    montant_ht: float,
    description: str,
    taux_tva: float = 8.1,
    date_emission: str = "",
    delai_paiement_jours: int = 30,
) -> str:
    """Crée une nouvelle facture et l'enregistre dans la base."""
    client = _trouver_client(id_client)
    if not client:
        return f"Client introuvable : {id_client}"

    try:
        ht = round(float(montant_ht), 2)
    except (ValueError, TypeError):
        return f"Montant HT invalide : {montant_ht}"

    if date_emission:
        try:
            d_em = datetime.strptime(date_emission, "%Y-%m-%d").date()
        except ValueError:
            return f"Date d'émission invalide : {date_emission}"
    else:
        d_em = date.today()
    d_ech = d_em + timedelta(days=delai_paiement_jours)

    factures = _charger_factures()
    # Numéro auto : FA-YYYY-NNN
    annee = d_em.year
    existants = [f["numero"] for f in factures if f["numero"].startswith(f"FA-{annee}-")]
    next_n = len(existants) + 1
    numero = f"FA-{annee}-{next_n:03d}"

    tva = round(ht * taux_tva / 100, 2)
    ttc = round(ht + tva, 2)

    nouvelle = {
        "numero": numero,
        "id_client": id_client.upper(),
        "date_emission": d_em.isoformat(),
        "date_echeance": d_ech.isoformat(),
        "montant_ht": f"{ht:.2f}",
        "taux_tva": f"{taux_tva}",
        "montant_tva": f"{tva:.2f}",
        "montant_ttc": f"{ttc:.2f}",
        "description": description,
        "statut": "impayee",
        "date_paiement": "",
    }
    factures.append(nouvelle)
    _ecrire_factures(factures)

    # Document texte
    doc = _generer_document_facture(nouvelle, client)
    chemin = FACTURES_GEN_DIR / f"{numero}.txt"
    chemin.write_text(doc, encoding="utf-8")

    return (
        f"✅ Facture {numero} créée pour {client['nom']}\n"
        f"   HT  : {_fmt(ht)} CHF\n"
        f"   TVA : {_fmt(tva)} CHF ({taux_tva}%)\n"
        f"   TTC : {_fmt(ttc)} CHF\n"
        f"   Échéance : {d_ech.strftime('%d/%m/%Y')}\n"
        f"   Document : {chemin.name}\n\n"
        f"--- APERÇU ---\n{doc}"
    )


def _generer_document_facture(f: dict, client: dict) -> str:
    """Génère le document texte d'une facture."""
    lignes = [
        f"{ENTREPRISE['nom']}",
        f"{ENTREPRISE['adresse']}",
        f"{ENTREPRISE['npa']} {ENTREPRISE['ville']} - {ENTREPRISE['pays']}",
        f"N° TVA : {ENTREPRISE['no_tva']}",
        "",
        "=" * 60,
        f"FACTURE  N° {f['numero']}",
        "=" * 60,
        "",
        "ÉMETTEUR :",
        f"  {ENTREPRISE['nom']}",
        f"  {ENTREPRISE['adresse']}, {ENTREPRISE['npa']} {ENTREPRISE['ville']}",
        "",
        "DESTINATAIRE :",
        f"  {client['nom']}",
        f"  {client['contact']}",
        f"  {client['adresse']}, {client['npa']} {client['ville']}",
        f"  N° TVA : {client.get('no_tva', '-')}",
        "",
        f"Date d'émission  : {datetime.strptime(f['date_emission'], '%Y-%m-%d').strftime('%d/%m/%Y')}",
        f"Date d'échéance  : {datetime.strptime(f['date_echeance'], '%Y-%m-%d').strftime('%d/%m/%Y')}",
        "",
        "─" * 60,
        f"  Description : {f['description']}",
        "─" * 60,
        "",
        f"  Montant HT       : {_fmt(float(f['montant_ht']))} CHF",
        f"  TVA ({f['taux_tva']}%)        : {_fmt(float(f['montant_tva']))} CHF",
        f"  ────────────────────────────────────",
        f"  Montant TTC      : {_fmt(float(f['montant_ttc']))} CHF",
        "",
        "PAIEMENT :",
        f"  IBAN : {ENTREPRISE['iban']}",
        f"  BIC  : {ENTREPRISE['bic']}",
        f"  Référence : {f['numero']}",
        "",
        f"Pour toute question : {ENTREPRISE['email']} / {ENTREPRISE['telephone']}",
        "",
        "Merci de votre confiance.",
    ]
    return "\n".join(lignes)


# ----------------------------------------------------------------------
# Outil 2 — Lister les factures
# ----------------------------------------------------------------------
def lister_factures(statut: str = "impayee") -> str:
    """Liste les factures par statut (impayee, payee, retard, tout)."""
    factures = _charger_factures()
    if not factures:
        return "Aucune facture dans la base."

    today = date.today()
    statut_l = statut.lower().strip()

    cibles = []
    for f in factures:
        d_ech = datetime.strptime(f["date_echeance"], "%Y-%m-%d").date()
        en_retard = (f["statut"] == "impayee" and d_ech < today)
        if statut_l == "tout":
            cibles.append((f, d_ech, en_retard))
        elif statut_l == "retard" and en_retard:
            cibles.append((f, d_ech, en_retard))
        elif statut_l == "impayee" and f["statut"] == "impayee":
            cibles.append((f, d_ech, en_retard))
        elif statut_l == "payee" and f["statut"] == "payee":
            cibles.append((f, d_ech, en_retard))

    if not cibles:
        return f"Aucune facture avec le statut '{statut}'."

    total_ht = sum(float(f["montant_ht"]) for f, _, _ in cibles)
    total_ttc = sum(float(f["montant_ttc"]) for f, _, _ in cibles)

    out = [f"=== Factures ({statut}) — {len(cibles)} facture(s) ===\n"]
    for f, d_ech, en_retard in sorted(cibles, key=lambda x: x[0]["date_echeance"]):
        client = _trouver_client(f["id_client"])
        nom_cli = client["nom"] if client else f["id_client"]
        marqueur = " 🔴 RETARD" if en_retard else ("" if f["statut"] == "impayee" else " ✅")
        jours = (d_ech - today).days
        ind_jours = (
            f"({-jours} j de retard)" if en_retard
            else (f"(échéance dans {jours} j)" if f["statut"] == "impayee" else "")
        )
        out.append(
            f"• {f['numero']}{marqueur}\n"
            f"   Client    : {nom_cli}\n"
            f"   Montant   : {_fmt(float(f['montant_ttc']))} CHF TTC "
            f"(HT {_fmt(float(f['montant_ht']))} + TVA {f['taux_tva']}%)\n"
            f"   Échéance  : {d_ech.strftime('%d/%m/%Y')} {ind_jours}\n"
            f"   Objet     : {f['description']}"
        )

    out.append(f"\n📊 TOTAL HT  : {_fmt(total_ht)} CHF")
    out.append(f"📊 TOTAL TTC : {_fmt(total_ttc)} CHF")
    return "\n".join(out)


# ----------------------------------------------------------------------
# Outil 3 — Marquer une facture comme payée
# ----------------------------------------------------------------------
def marquer_facture_payee(numero: str, date_paiement: str = "") -> str:
    """Marque une facture comme payée."""
    factures = _charger_factures()
    for f in factures:
        if f["numero"].upper() == numero.upper():
            f["statut"] = "payee"
            f["date_paiement"] = date_paiement or date.today().isoformat()
            _ecrire_factures(factures)
            return f"✅ Facture {numero} marquée comme PAYÉE le {f['date_paiement']}."
    return f"Facture introuvable : {numero}"


# ----------------------------------------------------------------------
# Outil 4 — Générer un texte de relance
# ----------------------------------------------------------------------
def generer_relance(numero: str, niveau: int = 1) -> str:
    """
    Génère un texte de relance pour une facture impayée.
    Niveau 1 : amical / Niveau 2 : ferme / Niveau 3 : mise en demeure.
    """
    f = _trouver_facture(numero)
    if not f:
        return f"Facture introuvable : {numero}"
    if f["statut"] == "payee":
        return f"La facture {numero} est déjà payée."

    client = _trouver_client(f["id_client"])
    if not client:
        return f"Client introuvable pour la facture {numero}."

    today = date.today()
    d_ech = datetime.strptime(f["date_echeance"], "%Y-%m-%d").date()
    jours_retard = max(0, (today - d_ech).days)

    en_tete = (
        f"À : {client['contact']} <{client['email']}>\n"
        f"De : {ENTREPRISE['nom']} <{ENTREPRISE['email']}>\n"
        f"Objet : Rappel — Facture {numero} en attente de règlement\n"
        f"Date : {today.strftime('%d/%m/%Y')}\n"
        f"\n"
    )

    montant = _fmt(float(f["montant_ttc"]))

    if niveau == 1:
        corps = (
            f"Bonjour {client['contact']},\n\n"
            f"Sauf erreur de notre part, le règlement de la facture {numero} "
            f"d'un montant de {montant} CHF TTC, émise le "
            f"{datetime.strptime(f['date_emission'], '%Y-%m-%d').strftime('%d/%m/%Y')}, "
            f"n'est pas encore parvenu sur notre compte.\n\n"
            f"Pourriez-vous nous indiquer si vous avez procédé au paiement ? "
            f"Si ce n'est pas le cas, nous vous remercions de bien vouloir le régler "
            f"dès que possible.\n\n"
            f"Coordonnées de paiement :\n"
            f"  IBAN : {ENTREPRISE['iban']}\n"
            f"  Référence : {numero}\n\n"
            f"Pour toute question, n'hésitez pas à nous contacter.\n\n"
            f"Cordialement,\n"
            f"{ENTREPRISE['nom']}\n"
            f"{ENTREPRISE['email']}"
        )
    elif niveau == 2:
        corps = (
            f"Bonjour {client['contact']},\n\n"
            f"Malgré notre précédent rappel, nous constatons que la facture {numero} "
            f"d'un montant de {montant} CHF TTC, échue depuis le "
            f"{d_ech.strftime('%d/%m/%Y')} (soit {jours_retard} jours), "
            f"reste impayée.\n\n"
            f"Nous vous prions de procéder à son règlement sous 10 jours, "
            f"faute de quoi nous serions contraints d'engager une procédure de recouvrement.\n\n"
            f"Coordonnées de paiement :\n"
            f"  IBAN : {ENTREPRISE['iban']}\n"
            f"  Référence : {numero}\n\n"
            f"Si le paiement a déjà été effectué, merci de nous en transmettre la preuve.\n\n"
            f"Cordialement,\n"
            f"{ENTREPRISE['nom']}"
        )
    else:  # niveau 3
        corps = (
            f"À l'attention de {client['contact']},\n\n"
            f"OBJET : MISE EN DEMEURE — Facture {numero}\n\n"
            f"Malgré nos précédentes relances, la facture {numero} d'un montant de "
            f"{montant} CHF TTC, échue depuis {jours_retard} jours, demeure impayée.\n\n"
            f"Conformément aux articles 102 et suivants du Code des Obligations suisse, "
            f"nous vous mettons en demeure de procéder au règlement intégral de cette "
            f"créance dans un délai de 10 jours à compter de la présente.\n\n"
            f"À défaut, nous nous réservons le droit d'engager toute procédure de "
            f"recouvrement, y compris des poursuites au sens de la LP, ainsi que "
            f"l'application d'intérêts moratoires au taux légal (5 %).\n\n"
            f"Coordonnées de paiement :\n"
            f"  IBAN : {ENTREPRISE['iban']}\n"
            f"  Référence : {numero}\n\n"
            f"Cordialement,\n"
            f"{ENTREPRISE['nom']}"
        )

    return en_tete + corps
