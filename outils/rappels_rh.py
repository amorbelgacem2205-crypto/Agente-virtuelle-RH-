"""
Outil : rappels RH (échéances importantes à venir).

Détecte automatiquement :
  - Fin de période d'essai (alerte 7 j avant + jour J)
  - Anniversaires d'embauche (1, 5, 10, 15, 20 ans)
  - Échéance de contrat CDD (alerte 30 j avant)
  - Évaluations annuelles (date d'embauche anniversaire mensuel)
"""

from datetime import date, datetime, timedelta
from .data_processor import _charger_employes


def _parse_date(s: str):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def lister_rappels(jours_a_venir: int = 30) -> str:
    """
    Renvoie tous les rappels RH dans les N prochains jours.
    Catégorisés par type.
    """
    employes = _charger_employes()
    if not employes:
        return "Aucune donnée employé disponible."

    today = date.today()
    horizon = today + timedelta(days=jours_a_venir)

    fin_essai = []
    anniversaires = []
    fin_cdd = []
    evaluations = []

    for e in employes:
        prenom_nom = f"{e['prenom']} {e['nom']} ({e['matricule']})"

        # 1) Fin de période d'essai
        d_essai = _parse_date(e.get("date_fin_periode_essai", ""))
        if d_essai and today <= d_essai <= horizon:
            jours = (d_essai - today).days
            fin_essai.append({
                "employe": prenom_nom,
                "date": d_essai,
                "jours_restants": jours,
                "poste": e["poste"],
            })

        # 2) Anniversaires d'embauche (1, 5, 10, 15, 20 ans)
        d_embauche = _parse_date(e["date_embauche"])
        if d_embauche:
            for nb_annees in (1, 5, 10, 15, 20, 25, 30):
                annivers = date(today.year, d_embauche.month, d_embauche.day)
                # gérer les 29 février
                if annivers < today:
                    try:
                        annivers = annivers.replace(year=today.year + 1)
                    except ValueError:
                        continue
                age_a_cette_date = annivers.year - d_embauche.year
                if age_a_cette_date == nb_annees and today <= annivers <= horizon:
                    anniversaires.append({
                        "employe": prenom_nom,
                        "date": annivers,
                        "annees": nb_annees,
                        "jours_restants": (annivers - today).days,
                    })

        # 3) Fin de CDD
        if e.get("type_contrat", "").upper() == "CDD":
            d_fin = _parse_date(e.get("date_fin_contrat", ""))
            if d_fin and today <= d_fin <= today + timedelta(days=60):
                fin_cdd.append({
                    "employe": prenom_nom,
                    "date": d_fin,
                    "jours_restants": (d_fin - today).days,
                    "poste": e["poste"],
                })

        # 4) Évaluation annuelle (date d'embauche anniversaire chaque année,
        #    pas seulement les 1/5/10 ans). On signale 14 j avant.
        if d_embauche:
            try:
                eval_date = date(today.year, d_embauche.month, d_embauche.day)
            except ValueError:
                continue
            if eval_date < today:
                try:
                    eval_date = eval_date.replace(year=today.year + 1)
                except ValueError:
                    continue
            if today <= eval_date <= horizon and (eval_date - today).days <= 14:
                evaluations.append({
                    "employe": prenom_nom,
                    "date": eval_date,
                    "jours_restants": (eval_date - today).days,
                    "annees_anciennete": eval_date.year - d_embauche.year,
                })

    # ---- Construction du rapport
    out = [f"=== Rappels RH des {jours_a_venir} prochains jours ({today.strftime('%d/%m/%Y')}) ===\n"]

    if fin_essai:
        out.append("⏰ FINS DE PÉRIODE D'ESSAI :")
        for r in sorted(fin_essai, key=lambda x: x["date"]):
            out.append(
                f"  • {r['employe']} — {r['poste']}\n"
                f"    Fin essai : {r['date'].strftime('%d/%m/%Y')} (J-{r['jours_restants']})"
            )
    else:
        out.append("⏰ Fins de période d'essai : aucune")
    out.append("")

    if anniversaires:
        out.append("🎉 ANNIVERSAIRES D'EMBAUCHE :")
        for r in sorted(anniversaires, key=lambda x: x["date"]):
            out.append(
                f"  • {r['employe']} — {r['annees']} ans dans l'entreprise\n"
                f"    Date : {r['date'].strftime('%d/%m/%Y')} (J-{r['jours_restants']})"
            )
    else:
        out.append("🎉 Anniversaires d'embauche (étapes clés 1/5/10/15/20 ans) : aucun")
    out.append("")

    if fin_cdd:
        out.append("📅 ÉCHÉANCES CDD (60 j) :")
        for r in sorted(fin_cdd, key=lambda x: x["date"]):
            out.append(
                f"  • {r['employe']} — {r['poste']}\n"
                f"    Fin contrat : {r['date'].strftime('%d/%m/%Y')} (J-{r['jours_restants']})"
            )
    else:
        out.append("📅 Échéances CDD (60 j) : aucune")
    out.append("")

    if evaluations:
        out.append("📝 ÉVALUATIONS ANNUELLES (14 j) :")
        for r in sorted(evaluations, key=lambda x: x["date"]):
            out.append(
                f"  • {r['employe']} — {r['annees_anciennete']} ans d'ancienneté\n"
                f"    Date : {r['date'].strftime('%d/%m/%Y')} (J-{r['jours_restants']})"
            )
    else:
        out.append("📝 Évaluations annuelles (14 j) : aucune")

    return "\n".join(out)


def prochains_anniversaires(jours: int = 90) -> str:
    """Liste les anniversaires d'embauche significatifs dans les N prochains jours."""
    employes = _charger_employes()
    today = date.today()
    horizon = today + timedelta(days=jours)
    rappels = []

    for e in employes:
        d_emb = _parse_date(e["date_embauche"])
        if not d_emb:
            continue
        for nb_annees in (1, 5, 10, 15, 20, 25, 30):
            try:
                annivers = date(today.year, d_emb.month, d_emb.day)
            except ValueError:
                continue
            if annivers < today:
                try:
                    annivers = annivers.replace(year=today.year + 1)
                except ValueError:
                    continue
            age_a_cette_date = annivers.year - d_emb.year
            if age_a_cette_date == nb_annees and today <= annivers <= horizon:
                rappels.append((annivers, e, nb_annees))

    if not rappels:
        return f"Aucun anniversaire d'embauche significatif dans les {jours} prochains jours."

    out = [f"🎉 Anniversaires d'embauche dans les {jours} prochains jours :\n"]
    for d_anniv, e, n in sorted(rappels):
        out.append(f"  • {d_anniv.strftime('%d/%m/%Y')} — {e['prenom']} {e['nom']} : {n} ans")
    return "\n".join(out)
