"""
Traitement des données RH (Suisse) — lecture du CSV employés, statistiques, recherche.
"""

import csv
from datetime import datetime
from pathlib import Path

DONNEES_DIR = Path(__file__).parent.parent / "donnees"
EMPLOYES_CSV = DONNEES_DIR / "employes.csv"


def _charger_employes() -> list[dict]:
    """Charge la base employés depuis le CSV."""
    if not EMPLOYES_CSV.exists():
        return []
    with open(EMPLOYES_CSV, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _annuel(emp: dict) -> float:
    """Calcule le salaire annuel brut en tenant compte du 13e."""
    nb_mois = 13 if str(emp.get("treizieme", "")).lower() in ("oui", "ja", "true", "1") else 12
    try:
        return float(emp["salaire_brut_mensuel_chf"]) * nb_mois
    except (ValueError, KeyError):
        return 0.0


def _fmt_chf(x: float) -> str:
    return f"{x:,.0f} CHF".replace(",", "'")


def statistiques_employes(metrique: str = "tout") -> str:
    """Retourne des statistiques sur les employés."""
    employes = _charger_employes()
    if not employes:
        return "Aucune donnée employé disponible."

    effectif = len(employes)
    par_service: dict[str, int] = {}
    par_canton: dict[str, int] = {}
    masse = 0.0
    anciennetes = []
    today = datetime.today()

    for e in employes:
        par_service[e["service"]] = par_service.get(e["service"], 0) + 1
        par_canton[e["canton"]] = par_canton.get(e["canton"], 0) + 1
        masse += _annuel(e)
        try:
            d = datetime.strptime(e["date_embauche"], "%Y-%m-%d")
            anciennetes.append((today - d).days / 365.25)
        except (ValueError, KeyError):
            pass

    anc_moy = sum(anciennetes) / len(anciennetes) if anciennetes else 0

    if metrique == "effectif":
        return f"Effectif total : {effectif} employés."
    if metrique == "par_service":
        lignes = [f"  - {s} : {n}" for s, n in sorted(par_service.items())]
        return f"Répartition par service ({effectif} employés) :\n" + "\n".join(lignes)
    if metrique == "par_canton":
        lignes = [f"  - {c} : {n}" for c, n in sorted(par_canton.items())]
        return f"Répartition par canton ({effectif} employés) :\n" + "\n".join(lignes)
    if metrique == "anciennete":
        return f"Ancienneté moyenne : {anc_moy:.1f} ans (sur {len(anciennetes)} employés)."
    if metrique == "masse_salariale":
        return f"Masse salariale annuelle brute : {_fmt_chf(masse)}"

    # tout
    lignes = [
        f"Effectif total : {effectif}",
        f"Ancienneté moyenne : {anc_moy:.1f} ans",
        f"Masse salariale brute annuelle : {_fmt_chf(masse)}",
        "Répartition par service :",
    ]
    for s, n in sorted(par_service.items()):
        lignes.append(f"  - {s} : {n}")
    lignes.append("Répartition par canton :")
    for c, n in sorted(par_canton.items()):
        lignes.append(f"  - {c} : {n}")
    return "\n".join(lignes)


def rechercher_employe(requete: str) -> str:
    """Recherche un employé par matricule, nom ou prénom."""
    employes = _charger_employes()
    requete_l = requete.strip().lower()
    resultats = [
        e for e in employes
        if requete_l in e["matricule"].lower()
        or requete_l in e["nom"].lower()
        or requete_l in e["prenom"].lower()
    ]
    if not resultats:
        return f"Aucun employé trouvé pour la recherche : '{requete}'."
    if len(resultats) > 5:
        return f"{len(resultats)} résultats. Précise ta recherche."

    out = []
    for e in resultats:
        annuel = _annuel(e)
        out.append(
            f"- {e['matricule']} | {e['prenom']} {e['nom']}\n"
            f"  Poste     : {e['poste']}\n"
            f"  Service   : {e['service']}  |  Canton : {e['canton']}\n"
            f"  Naissance : {e.get('date_naissance', '?')}\n"
            f"  Embauche  : {e['date_embauche']}\n"
            f"  Email     : {e['email']}\n"
            f"  No AVS    : {e.get('no_avs', '?')}\n"
            f"  Salaire   : {_fmt_chf(float(e['salaire_brut_mensuel_chf']))}/mois "
            f"({_fmt_chf(annuel)}/an, {'13e' if str(e.get('treizieme','')).lower() in ('oui','ja') else '12 mois'})\n"
            f"  Congés acquis : {e['conges_acquis']} j | pris : {e['conges_pris']} j"
        )
    return "\n\n".join(out)


def calculer_conges_restants(matricule: str) -> str:
    """Calcule le solde de congés restants d'un employé."""
    employes = _charger_employes()
    matricule_l = matricule.strip().upper()
    for e in employes:
        if e["matricule"].upper() == matricule_l:
            try:
                acquis = float(e["conges_acquis"])
                pris = float(e["conges_pris"])
                restant = acquis - pris
                return (
                    f"Solde de congés pour {e['prenom']} {e['nom']} ({e['matricule']}) :\n"
                    f"  - Acquis : {acquis:.1f} j\n"
                    f"  - Pris   : {pris:.1f} j\n"
                    f"  - Restant : {restant:.1f} j"
                )
            except ValueError:
                return f"Données de congés invalides pour {matricule}."
    return f"Matricule inconnu : {matricule}."
