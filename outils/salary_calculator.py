"""
Calculateur de salaire suisse — simulation brut → net.

Modèle simplifié multi-cantons :
  - AVS / AI / APG : taux fédéraux uniformes
  - AC (chômage) : 1,1 % jusqu'à 148 200 CHF, 0,5 % au-dessus (cotisation de solidarité)
  - LAA NBU (assurance accidents non professionnels) : à charge de l'employé
  - LPP (2e pilier) : barème légal par tranche d'âge (50 % employé / 50 % employeur)

⚠️ Simulation indicative seulement. Les taux exacts varient selon :
  - la caisse de pension (LPP)
  - l'assureur LAA
  - le canton (impôt à la source non inclus ici)
  - la convention collective de travail (CCT)

Pour un calcul officiel, faire valider par un fiduciaire.
"""

from datetime import date, datetime
from typing import Literal

# ----------------------------------------------------------------------
# Taux fédéraux 2024-2026
# ----------------------------------------------------------------------
TAUX = {
    "avs": 0.0435,           # 4,35 % côté employé
    "ai": 0.007,             # 0,7 %
    "apg": 0.0025,           # 0,25 %
    "ac": 0.011,             # 1,1 % jusqu'au plafond
    "ac_solidaire": 0.005,   # 0,5 % au-delà
    "laa_nbu": 0.0173,       # ~1,73 % médian (varie par assureur)
}
PLAFOND_AC = 148_200  # CHF/an au-delà : taux solidarité

# Barème LPP légal — taux total (employeur + employé) par tranche d'âge.
# La pratique : split 50/50, donc l'employé paie la moitié.
LPP_BANDES = [
    (25, 34, 0.07),
    (35, 44, 0.10),
    (45, 54, 0.15),
    (55, 65, 0.18),
]

# Liste des 26 cantons (codes officiels)
CANTONS_VALIDES = {
    "AG", "AI", "AR", "BE", "BL", "BS", "FR", "GE", "GL", "GR", "JU",
    "LU", "NE", "NW", "OW", "SG", "SH", "SO", "SZ", "TG", "TI", "UR",
    "VD", "VS", "ZG", "ZH",
}

# Cantons et leur(s) langue(s) officielle(s) (utile plus tard pour la doc/UX)
CANTONS_LANGUES = {
    "GE": "fr", "VD": "fr", "NE": "fr", "JU": "fr", "FR": "fr/de",
    "VS": "fr/de", "BE": "de/fr", "TI": "it", "GR": "de/it/rm",
    # Tout le reste : DE
    **{c: "de" for c in {"AG", "AI", "AR", "BL", "BS", "GL", "LU", "NW",
                         "OW", "SG", "SH", "SO", "SZ", "TG", "UR", "ZG", "ZH"}},
}


def _taux_lpp_total(age: int) -> float:
    """Taux LPP TOTAL (employeur + employé) selon âge."""
    for amin, amax, taux in LPP_BANDES:
        if amin <= age <= amax:
            return taux
    return 0.0  # < 25 ou > 65 : pas obligatoire


def _calculer_age(date_naissance: str) -> int:
    """Calcule l'âge à partir d'une date YYYY-MM-DD."""
    d = datetime.strptime(date_naissance, "%Y-%m-%d").date()
    today = date.today()
    return today.year - d.year - ((today.month, today.day) < (d.month, d.day))


def simuler_salaire(
    salaire_brut_mensuel: float,
    canton: str = "VD",
    age: int = 35,
    treizieme: bool = True,
    date_naissance: str = "",
) -> str:
    """
    Simule la décomposition brut → net pour un salaire suisse.

    Args:
        salaire_brut_mensuel : salaire mensuel brut en CHF
        canton : code canton (VD, GE, ZH, BE, …)
        age : âge de l'employé (sinon utiliser date_naissance)
        treizieme : True si l'employé reçoit un 13e salaire
        date_naissance : YYYY-MM-DD, calcule l'âge automatiquement si fourni

    Returns:
        Tableau formaté avec brut / cotisations / net.
    """
    try:
        brut_m = float(salaire_brut_mensuel)
    except (TypeError, ValueError):
        return f"Salaire brut invalide : {salaire_brut_mensuel}"

    canton = (canton or "VD").upper()
    if canton not in CANTONS_VALIDES:
        return f"Canton inconnu : {canton}. Cantons valides : {sorted(CANTONS_VALIDES)}"

    if date_naissance:
        try:
            age = _calculer_age(date_naissance)
        except ValueError:
            return f"Date de naissance invalide : {date_naissance}"

    nb_mois = 13 if treizieme else 12
    brut_a = brut_m * nb_mois

    # Cotisations sociales (part employé)
    avs = brut_a * TAUX["avs"]
    ai = brut_a * TAUX["ai"]
    apg = brut_a * TAUX["apg"]
    if brut_a <= PLAFOND_AC:
        ac = brut_a * TAUX["ac"]
    else:
        ac = PLAFOND_AC * TAUX["ac"] + (brut_a - PLAFOND_AC) * TAUX["ac_solidaire"]
    laa_nbu = brut_a * TAUX["laa_nbu"]

    # LPP : on prend la moitié du taux total (split 50/50 employeur/employé)
    lpp_total = _taux_lpp_total(age)
    lpp = brut_a * lpp_total / 2

    total_cotisations = avs + ai + apg + ac + laa_nbu + lpp
    net_a = brut_a - total_cotisations
    net_m = net_a / nb_mois

    pct = lambda x: (x / brut_a * 100) if brut_a else 0
    fmt = lambda x: f"{x:>12,.2f} CHF".replace(",", "'")

    lignes = [
        f"=== Simulation salaire — Canton {canton} ===",
        f"Hypothèses : âge {age} ans, {'13e' if treizieme else '12 mois'}, "
        f"langue principale du canton : {CANTONS_LANGUES.get(canton, '?')}",
        "",
        f"Salaire brut mensuel    : {fmt(brut_m)}",
        f"Salaire brut annuel     : {fmt(brut_a)}  ({nb_mois} mois)",
        "",
        "DÉDUCTIONS (part employé) :",
        f"  AVS  (4,35%)          : {fmt(avs)}    ({pct(avs):.2f} %)",
        f"  AI   (0,7%)           : {fmt(ai)}    ({pct(ai):.2f} %)",
        f"  APG  (0,25%)          : {fmt(apg)}    ({pct(apg):.2f} %)",
        f"  AC   (1,1% / 0,5%)    : {fmt(ac)}    ({pct(ac):.2f} %)",
        f"  LAA NBU (~1,73%)      : {fmt(laa_nbu)}    ({pct(laa_nbu):.2f} %)",
        f"  LPP  ({lpp_total*100:.0f}% total → 50%) : {fmt(lpp)}    ({pct(lpp):.2f} %)",
        f"  ─────────────────────────────────────────────────",
        f"  TOTAL DÉDUCTIONS      : {fmt(total_cotisations)}    ({pct(total_cotisations):.2f} %)",
        "",
        f"SALAIRE NET ANNUEL      : {fmt(net_a)}",
        f"SALAIRE NET MENSUEL     : {fmt(net_m)}",
        "",
        "⚠ Simulation indicative — n'inclut PAS l'impôt à la source.",
        "  Pour les non-résidents ou détenteurs de permis B/L/G, ajouter ~5-25 %",
        "  selon canton, situation familiale et revenu (barème cantonal).",
    ]
    return "\n".join(lignes)
