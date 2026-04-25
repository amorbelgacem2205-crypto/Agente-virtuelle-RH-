"""
Outil : génération d'une réponse email RH professionnelle.
Utilise Claude pour rédiger une réponse ton entreprise.
"""

import os
from anthropic import Anthropic

_client = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


PROMPT_EMAIL = """Tu es Léa, assistante RH. Rédige une réponse à l'email ci-dessous.

CONSIGNES :
- Ton : professionnel, chaleureux, tutoiement
- Structure : salutation -> réponse claire -> action concrète -> formule de politesse
- Maximum 200 mots
- Signe : "Léa - Service RH"
- Si la demande exige une décision RH (rupture, sanction, augmentation), oriente vers le DRH humain.
- Format de sortie : email prêt à envoyer (Objet + corps), rien d'autre.
"""


def repondre_email(email_recu: str, contexte: str = "") -> str:
    """Génère une réponse email professionnelle."""
    client = _get_client()
    contenu = f"EMAIL REÇU :\n{email_recu}\n"
    if contexte:
        contenu += f"\nCONTEXTE : {contexte}\n"
    contenu += "\nRédige maintenant la réponse."

    rep = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system=PROMPT_EMAIL,
        messages=[{"role": "user", "content": contenu}],
    )
    return "\n".join(b.text for b in rep.content if b.type == "text")
