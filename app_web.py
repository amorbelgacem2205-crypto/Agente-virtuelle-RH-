"""
Interface web Streamlit pour Léa — Agente Virtuelle RH (Suisse).

Lancement :
    streamlit run app_web.py

Le navigateur s'ouvre automatiquement sur http://localhost:8501
"""

import os
import re
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv

# 1. Charger les variables d'environnement depuis .env (mode local)
load_dotenv()

# 2. Si on tourne sur Streamlit Cloud, charger les secrets dans os.environ
#    (les modules outils utilisent os.getenv, donc on bridge st.secrets → os.environ)
try:
    for cle in ("ANTHROPIC_API_KEY", "LANGUE",
                "GMAIL_ADDRESS", "GMAIL_APP_PASSWORD",
                "OUTLOOK_ADDRESS", "OUTLOOK_APP_PASSWORD"):
        if cle in st.secrets:
            os.environ[cle] = str(st.secrets[cle])
except (FileNotFoundError, AttributeError, st.errors.StreamlitSecretNotFoundError):
    pass  # Pas de fichier secrets (mode local pur), on utilise déjà .env

# 3. Vérification de la clé API
if not os.getenv("ANTHROPIC_API_KEY"):
    st.error(
        "⚠️ La clé **ANTHROPIC_API_KEY** n'est pas configurée.\n\n"
        "**Localement** : crée un fichier `.env` à partir de `.env.example`.\n\n"
        "**Sur Streamlit Cloud** : clique sur les 3 points en haut à droite → "
        "**Settings** → **Secrets** → ajoute :\n\n"
        "```toml\n"
        'ANTHROPIC_API_KEY = "sk-ant-api03-..."\n'
        'LANGUE = "FR"\n'
        "```"
    )
    st.stop()

from agente_rh import AgenteRH

# ----------------------------------------------------------------------
# Textes de l'interface (FR / DE)
# ----------------------------------------------------------------------
TEXTES = {
    "FR": {
        "titre": "Léa — Assistante RH virtuelle 🇨🇭",
        "sous_titre": "Ton assistante RH propulsée par l'IA",
        "sidebar_titre": "⚙️ Paramètres",
        "langue_label": "Langue",
        "nouvelle_conv": "🔄 Nouvelle conversation",
        "outils_label": "🛠 Outils disponibles",
        "exemples_label": "💡 Exemples de questions",
        "exemples": [
            "Donne-moi la masse salariale par canton",
            "Combien de vacances reste-t-il à EMP005 ?",
            "Quel salaire net pour 8500 CHF brut/mois à Genève à 35 ans ?",
            "Quelle est notre politique de télétravail ?",
            "Génère une attestation de travail pour EMP003",
            "Qui est EMP010 ?",
        ],
        "input_placeholder": "Pose ta question à Léa…",
        "thinking": "Léa réfléchit…",
        "tool_used": "Outils utilisés",
        "footer": "💡 Léa est une assistante. Toute décision RH sensible reste de la responsabilité du DRH humain.",
    },
    "DE": {
        "titre": "Lea — Virtuelle HR-Assistentin 🇨🇭",
        "sous_titre": "Deine HR-Assistentin mit KI",
        "sidebar_titre": "⚙️ Einstellungen",
        "langue_label": "Sprache",
        "nouvelle_conv": "🔄 Neue Unterhaltung",
        "outils_label": "🛠 Verfügbare Tools",
        "exemples_label": "💡 Beispielfragen",
        "exemples": [
            "Zeig mir die Lohnsumme pro Kanton",
            "Wie viele Ferientage hat EMP005 noch?",
            "Wie hoch ist der Nettolohn bei 8500 CHF brutto in Zürich, 35 Jahre?",
            "Wie ist unsere Homeoffice-Richtlinie?",
            "Erstelle eine Arbeitsbestätigung für EMP003",
            "Wer ist EMP010?",
        ],
        "input_placeholder": "Stelle Lea eine Frage…",
        "thinking": "Lea denkt nach…",
        "tool_used": "Verwendete Tools",
        "footer": "💡 Lea ist eine Assistentin. Sensible HR-Entscheidungen liegen weiterhin bei der menschlichen HR-Leitung.",
    },
}

# ----------------------------------------------------------------------
# Configuration de la page
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="Léa — Assistante RH",
    page_icon="👩‍💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Style CSS perso
st.markdown(
    """
    <style>
    .stChatMessage { font-size: 15px; }
    .tool-badge {
        display: inline-block;
        padding: 2px 8px;
        margin: 2px 4px 2px 0;
        background: #f0f2f6;
        border-radius: 12px;
        font-size: 11px;
        color: #555;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------
# Initialisation session
# ----------------------------------------------------------------------
if "langue" not in st.session_state:
    st.session_state.langue = (os.getenv("LANGUE") or "FR").upper()

T = TEXTES[st.session_state.langue]

if "agente" not in st.session_state:
    st.session_state.agente = AgenteRH(langue=st.session_state.langue)
    st.session_state.messages = []

# ----------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------
with st.sidebar:
    st.markdown(f"### {T['sidebar_titre']}")

    nouvelle_langue = st.radio(
        T["langue_label"],
        options=["FR", "DE"],
        index=0 if st.session_state.langue == "FR" else 1,
        horizontal=True,
    )
    if nouvelle_langue != st.session_state.langue:
        st.session_state.langue = nouvelle_langue
        st.session_state.agente = AgenteRH(langue=nouvelle_langue)
        st.session_state.messages = []
        st.rerun()

    if st.button(T["nouvelle_conv"], use_container_width=True):
        st.session_state.agente = AgenteRH(langue=st.session_state.langue)
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.markdown(f"#### {T['outils_label']}")
    outils_dispo = [
        ("📊", "Statistiques RH"),
        ("👤", "Recherche employé"),
        ("🏖", "Solde vacances"),
        ("💰", "Simulation salaire suisse"),
        ("📋", "FAQ politique RH"),
        ("📄", "Documents RH (attestations)"),
        ("📧", "Lecture/réponse emails"),
        ("🎯", "Screening de CV"),
    ]
    for emoji, nom in outils_dispo:
        st.markdown(f"{emoji}  {nom}")

    st.divider()
    st.markdown(f"#### {T['exemples_label']}")
    for ex in T["exemples"]:
        if st.button(ex, key=f"ex_{ex}", use_container_width=True):
            st.session_state.exemple_clique = ex
            st.rerun()

# ----------------------------------------------------------------------
# Zone principale
# ----------------------------------------------------------------------
col1, col2 = st.columns([3, 1])
with col1:
    st.title(T["titre"])
    st.caption(T["sous_titre"])

# Helper : détecte les fichiers générés et affiche un bouton de téléchargement
FICHIER_PATTERN = re.compile(r"📎 FICHIER\s*:\s*(.+)")

def _afficher_telechargements(contenu: str):
    """Cherche les fichiers signalés par '📎 FICHIER : ...' et offre un bouton de téléchargement."""
    for match in FICHIER_PATTERN.finditer(contenu):
        chemin = Path(match.group(1).strip())
        if chemin.exists() and chemin.is_file():
            with open(chemin, "rb") as f:
                data = f.read()
            mime_map = {
                ".pdf": "application/pdf",
                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ".txt": "text/plain",
            }
            mime = mime_map.get(chemin.suffix.lower(), "application/octet-stream")
            st.download_button(
                label=f"⬇️ Télécharger {chemin.name}",
                data=data,
                file_name=chemin.name,
                mime=mime,
                key=f"dl_{chemin.name}_{hash(contenu)}",
                use_container_width=False,
            )

def _nettoyer_message(contenu: str) -> str:
    """Retire les marqueurs FICHIER pour l'affichage en chat."""
    return FICHIER_PATTERN.sub("", contenu).rstrip()


# Affichage de l'historique
for msg in st.session_state.messages:
    avatar = "👤" if msg["role"] == "user" else "👩‍💼"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(_nettoyer_message(msg["content"]))
        _afficher_telechargements(msg["content"])
        if msg.get("outils"):
            badges = " ".join(
                f'<span class="tool-badge">🛠 {o}</span>' for o in msg["outils"]
            )
            st.markdown(
                f'<div style="margin-top:6px;font-size:11px;color:#888;">'
                f'{T["tool_used"]} : {badges}</div>',
                unsafe_allow_html=True,
            )

# Récupération de l'input (depuis exemple cliqué OU saisie manuelle)
prompt = None
if "exemple_clique" in st.session_state:
    prompt = st.session_state.pop("exemple_clique")

manual = st.chat_input(T["input_placeholder"])
if manual:
    prompt = manual

# Traitement du message
if prompt:
    # Affichage immédiat du message utilisateur
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    # Réponse de Léa
    with st.chat_message("assistant", avatar="👩‍💼"):
        with st.spinner(T["thinking"]):
            try:
                reponse = st.session_state.agente.chat(prompt, verbose=False)
                outils = list(st.session_state.agente.dernier_outils_utilises)
            except Exception as e:
                reponse = f"❌ Erreur : {e}"
                outils = []
        st.markdown(_nettoyer_message(reponse))
        _afficher_telechargements(reponse)
        if outils:
            badges = " ".join(f'<span class="tool-badge">🛠 {o}</span>' for o in outils)
            st.markdown(
                f'<div style="margin-top:6px;font-size:11px;color:#888;">'
                f'{T["tool_used"]} : {badges}</div>',
                unsafe_allow_html=True,
            )

    st.session_state.messages.append(
        {"role": "assistant", "content": reponse, "outils": outils}
    )

# Footer
st.divider()
st.caption(T["footer"])
