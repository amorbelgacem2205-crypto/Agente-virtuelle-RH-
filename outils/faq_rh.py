"""
Outil : consultation de la base de connaissances RH (politique de l'entreprise).
Bilingue : charge le fichier FR ou DE selon la variable LANGUE (.env).
"""

import os
from pathlib import Path
from anthropic import Anthropic

DONNEES_DIR = Path(__file__).parent.parent / "donnees"

_client = None
_politique_cache: dict[str, str] = {}


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


def _langue_courante() -> str:
    """Renvoie 'FR' ou 'DE' selon la variable d'environnement LANGUE."""
    langue = (os.getenv("LANGUE") or "FR").upper()
    return "DE" if langue == "DE" else "FR"


def _charger_politique() -> str:
    """Charge la politique RH dans la langue active (FR par défaut)."""
    langue = _langue_courante()
    if langue in _politique_cache:
        return _politique_cache[langue]
    fichier = DONNEES_DIR / f"politique_rh_{langue.lower()}.md"
    if fichier.exists():
        contenu = fichier.read_text(encoding="utf-8")
    else:
        contenu = ""
    _politique_cache[langue] = contenu
    return contenu


PROMPTS_FAQ = {
    "FR": """Tu réponds à une question d'employé sur la politique RH de l'entreprise,
en t'appuyant UNIQUEMENT sur le document fourni.

Règles :
- Si la réponse est dans le document, cite la section concernée.
- Si elle n'y est pas, dis-le clairement et propose de contacter le DRH.
- Réponse concise (max 150 mots), claire, en français suisse, ton tutoiement professionnel.
""",
    "DE": """Du beantwortest eine Frage eines Mitarbeiters zur HR-Richtlinie des Unternehmens,
ausschliesslich auf Basis des bereitgestellten Dokuments.

Regeln:
- Wenn die Antwort im Dokument steht, zitiere den betroffenen Abschnitt.
- Wenn nicht, sage es klar und schlage vor, die HR-Leitung zu kontaktieren.
- Knappe Antwort (max. 150 Wörter), klar, in Schweizerdeutsch-Standard, Du-Form professionell.
""",
}


def consulter_politique_rh(question: str) -> str:
    """Répond à une question sur la politique RH dans la langue active."""
    politique = _charger_politique()
    if not politique:
        return ("La base de connaissances RH n'est pas disponible. "
                "Merci de contacter directement le service RH.")

    langue = _langue_courante()
    contenu = (
        f"DOCUMENT DE POLITIQUE RH ({langue}) :\n{politique}\n\n"
        f"---\n\nQUESTION : {question}\n\n"
    )
    client = _get_client()
    rep = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=800,
        system=PROMPTS_FAQ[langue],
        messages=[{"role": "user", "content": contenu}],
    )
    return "\n".join(b.text for b in rep.content if b.type == "text")
