"""
Outil : génération de documents RH officiels.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from .data_processor import _charger_employes

DOCUMENTS_DIR = Path(__file__).parent.parent / "documents_generes"
DOCUMENTS_DIR.mkdir(exist_ok=True)

NOM_ENTREPRISE = "ACME France SAS"
ADRESSE_ENTREPRISE = "12 rue de l'Innovation, 75008 Paris"
SIRET = "123 456 789 00012"
SIGNATAIRE = "Léa MARTIN — Directrice des Ressources Humaines"


def _trouver_employe(matricule: str) -> dict | None:
    matricule_l = matricule.strip().upper()
    for e in _charger_employes():
        if e["matricule"].upper() == matricule_l:
            return e
    return None


def _entete() -> str:
    return (
        f"{NOM_ENTREPRISE}\n"
        f"{ADRESSE_ENTREPRISE}\n"
        f"SIRET : {SIRET}\n\n"
        f"Fait à Paris, le {datetime.today().strftime('%d/%m/%Y')}\n\n"
    )


def _pied() -> str:
    return f"\n\n{SIGNATAIRE}\n[Signature et cachet]"


def _attestation_travail(emp: dict, details: str) -> str:
    return (
        _entete()
        + "ATTESTATION DE TRAVAIL\n"
        + "=" * 30
        + "\n\n"
        + f"Je soussigné(e), {SIGNATAIRE}, atteste que :\n\n"
        + f"{emp['prenom']} {emp['nom']} (matricule {emp['matricule']})\n"
        + f"est employé(e) au sein de {NOM_ENTREPRISE} depuis le {emp['date_embauche']},\n"
        + f"en qualité de {emp['poste']}, au sein du service {emp['service']}.\n\n"
        + (f"Précisions : {details}\n\n" if details else "")
        + "La présente attestation est délivrée à l'intéressé(e) pour servir et valoir ce que de droit.\n"
        + _pied()
    )


def _attestation_salaire(emp: dict, details: str) -> str:
    return (
        _entete()
        + "ATTESTATION DE SALAIRE\n"
        + "=" * 30
        + "\n\n"
        + f"Je soussigné(e), {SIGNATAIRE}, atteste que :\n\n"
        + f"{emp['prenom']} {emp['nom']} (matricule {emp['matricule']})\n"
        + f"perçoit un salaire brut annuel de {float(emp['salaire_brut_annuel']):,.0f} €,\n".replace(",", " ")
        + f"au titre de son poste de {emp['poste']} occupé depuis le {emp['date_embauche']}.\n\n"
        + (f"Précisions : {details}\n\n" if details else "")
        + "La présente attestation est remise à l'intéressé(e) pour servir et valoir ce que de droit.\n"
        + _pied()
    )


def _certificat_travail(emp: dict, details: str) -> str:
    return (
        _entete()
        + "CERTIFICAT DE TRAVAIL\n"
        + "=" * 30
        + "\n\n"
        + f"Je soussigné(e), {SIGNATAIRE}, certifie que :\n\n"
        + f"{emp['prenom']} {emp['nom']} (matricule {emp['matricule']})\n"
        + f"a été employé(e) au sein de {NOM_ENTREPRISE} à compter du {emp['date_embauche']},\n"
        + f"en qualité de {emp['poste']} (service {emp['service']}).\n\n"
        + (f"Motif de fin de contrat : {details}\n\n" if details else "")
        + "L'intéressé(e) quitte l'entreprise libre de tout engagement.\n"
        + _pied()
    )


def _lettre_promotion(emp: dict, details: str) -> str:
    return (
        _entete()
        + f"Objet : Promotion\n\n"
        + f"Cher(e) {emp['prenom']} {emp['nom']},\n\n"
        + f"Nous avons le plaisir de vous annoncer votre promotion au sein de "
        + f"{NOM_ENTREPRISE}.\n\n"
        + (f"Détails : {details}\n\n" if details else "")
        + f"Cette évolution prendra effet à compter du {datetime.today().strftime('%d/%m/%Y')}.\n"
        + "L'ensemble des modalités sera précisé dans un avenant à votre contrat de travail.\n\n"
        + "Toutes nos félicitations pour cette belle évolution.\n"
        + _pied()
    )


GENERATEURS = {
    "attestation_travail": _attestation_travail,
    "attestation_salaire": _attestation_salaire,
    "certificat_travail": _certificat_travail,
    "lettre_promotion": _lettre_promotion,
}


def generer_document_rh(type_document: str, matricule: str, details: str = "") -> str:
    """Génère un document RH et l'enregistre dans documents_generes/."""
    if type_document not in GENERATEURS:
        return f"Type de document inconnu : {type_document}"
    emp = _trouver_employe(matricule)
    if not emp:
        return f"Matricule introuvable : {matricule}"

    contenu = GENERATEURS[type_document](emp, details)
    nom_fichier = (
        f"{type_document}_{emp['matricule']}_{datetime.today().strftime('%Y%m%d')}.txt"
    )
    chemin = DOCUMENTS_DIR / nom_fichier
    chemin.write_text(contenu, encoding="utf-8")

    return (
        f"Document généré et enregistré : {chemin.name}\n"
        f"Chemin : {chemin}\n\n"
        f"--- APERÇU ---\n{contenu}"
    )
