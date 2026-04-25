"""
Outil : pré-screening de CV par rapport à une fiche de poste.
Utilise Claude pour analyser et scorer.
"""

import os
from anthropic import Anthropic

_client = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


PROMPT_SCREENING = """Tu es un expert en recrutement. Analyse la pertinence du CV par rapport à la fiche de poste.

Renvoie ta réponse au format suivant exactement :

SCORE : X/100
NIVEAU : [Excellent / Bon / Moyen / Faible]

POINTS FORTS :
- ...
- ...

POINTS FAIBLES :
- ...
- ...

COMPÉTENCES MANQUANTES :
- ...

RECOMMANDATION : [Convoquer en entretien / Convoquer si pas de meilleur profil / Écarter]

JUSTIFICATION (2-3 phrases) :
...

Sois objectif, factuel et bienveillant. Évite tout biais discriminatoire (âge, genre, origine).
"""


def screener_cv(cv_texte: str, fiche_poste: str) -> str:
    """Analyse un CV par rapport à une fiche de poste."""
    client = _get_client()
    contenu = (
        f"FICHE DE POSTE :\n{fiche_poste}\n\n"
        f"---\n\n"
        f"CV DU CANDIDAT :\n{cv_texte}\n\n"
        f"Analyse maintenant."
    )
    rep = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1500,
        system=PROMPT_SCREENING,
        messages=[{"role": "user", "content": contenu}],
    )
    return "\n".join(b.text for b in rep.content if b.type == "text")
