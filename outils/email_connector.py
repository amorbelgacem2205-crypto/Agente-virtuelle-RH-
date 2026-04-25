"""
Connecteur email IMAP + SMTP, compatible Gmail ET Outlook/Microsoft 365.

L'agente peut :
  - lire les emails récents (lire_emails_recents)
  - lire le contenu complet d'un email précis (lire_email)
  - envoyer un email (envoyer_email)
  - enregistrer un brouillon de réponse dans le dossier Brouillons (creer_brouillon)

Le choix du fournisseur (gmail / outlook) est passé en paramètre.

Configuration (variables d'environnement) :
  - GMAIL_ADDRESS       / GMAIL_APP_PASSWORD
  - OUTLOOK_ADDRESS     / OUTLOOK_APP_PASSWORD

Pour Gmail   : https://myaccount.google.com/apppasswords (2FA requise)
Pour Outlook : https://account.live.com/proofs/AppPassword (2FA requise)
"""

import os
import imaplib
import smtplib
import ssl
from email.message import EmailMessage
from email import message_from_bytes
from email.header import decode_header
from datetime import datetime
from time import time

# ----------------------------------------------------------------------
# Paramètres serveurs
# ----------------------------------------------------------------------
PROVIDERS = {
    "gmail": {
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "drafts_folder": '"[Gmail]/Drafts"',
        "env_address": "GMAIL_ADDRESS",
        "env_password": "GMAIL_APP_PASSWORD",
    },
    "outlook": {
        "imap_host": "outlook.office365.com",
        "imap_port": 993,
        "smtp_host": "smtp.office365.com",
        "smtp_port": 587,
        "drafts_folder": '"Drafts"',
        "env_address": "OUTLOOK_ADDRESS",
        "env_password": "OUTLOOK_APP_PASSWORD",
    },
}


def _get_credentials(provider: str) -> tuple[str, str, dict]:
    """Récupère adresse + mot de passe pour le provider donné."""
    p = provider.lower().strip()
    if p not in PROVIDERS:
        raise ValueError(f"Provider non supporté : {provider}. Utilise 'gmail' ou 'outlook'.")
    cfg = PROVIDERS[p]
    addr = os.getenv(cfg["env_address"])
    pwd = os.getenv(cfg["env_password"])
    if not addr or not pwd:
        raise RuntimeError(
            f"Identifiants {p} non configurés. Définis {cfg['env_address']} et "
            f"{cfg['env_password']} dans le fichier .env."
        )
    return addr, pwd, cfg


def _decode(s) -> str:
    """Décode un en-tête email (peut être bytes encodés)."""
    if s is None:
        return ""
    parts = decode_header(s)
    out = ""
    for chunk, enc in parts:
        if isinstance(chunk, bytes):
            try:
                out += chunk.decode(enc or "utf-8", errors="replace")
            except (LookupError, TypeError):
                out += chunk.decode("utf-8", errors="replace")
        else:
            out += chunk
    return out


def _extraire_corps(msg) -> str:
    """Extrait le corps texte d'un message email."""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition", ""))
            if ctype == "text/plain" and "attachment" not in disp:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        # fallback : html
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        return ""
    payload = msg.get_payload(decode=True)
    if payload:
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    return str(msg.get_payload())


# ----------------------------------------------------------------------
# Lecture (IMAP)
# ----------------------------------------------------------------------
def lire_emails_recents(provider: str, limite: int = 5, dossier: str = "INBOX") -> str:
    """Liste les N derniers emails du dossier."""
    try:
        addr, pwd, cfg = _get_credentials(provider)
        limite = max(1, min(int(limite), 50))

        with imaplib.IMAP4_SSL(cfg["imap_host"], cfg["imap_port"]) as imap:
            imap.login(addr, pwd)
            imap.select(dossier, readonly=True)
            typ, data = imap.search(None, "ALL")
            if typ != "OK":
                return "Impossible de lister les emails."
            ids = data[0].split()
            derniers = ids[-limite:][::-1]  # plus récents d'abord

            lignes = [f"=== {len(derniers)} derniers emails ({provider} / {dossier}) ==="]
            for num in derniers:
                typ, data = imap.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
                if typ != "OK" or not data or not data[0]:
                    continue
                hdr = data[0][1]
                msg = message_from_bytes(hdr)
                lignes.append(
                    f"\n[ID {num.decode()}]\n"
                    f"  De      : {_decode(msg.get('From'))}\n"
                    f"  Objet   : {_decode(msg.get('Subject'))}\n"
                    f"  Date    : {_decode(msg.get('Date'))}"
                )
            return "\n".join(lignes)
    except Exception as e:
        return f"Erreur lecture {provider} : {e}"


def lire_email(provider: str, message_id: str) -> str:
    """Récupère le contenu complet d'un email donné."""
    try:
        addr, pwd, cfg = _get_credentials(provider)
        with imaplib.IMAP4_SSL(cfg["imap_host"], cfg["imap_port"]) as imap:
            imap.login(addr, pwd)
            imap.select("INBOX", readonly=True)
            typ, data = imap.fetch(str(message_id).encode(), "(RFC822)")
            if typ != "OK" or not data or not data[0]:
                return f"Email ID {message_id} introuvable."
            msg = message_from_bytes(data[0][1])
            corps = _extraire_corps(msg)
            return (
                f"De      : {_decode(msg.get('From'))}\n"
                f"À       : {_decode(msg.get('To'))}\n"
                f"Objet   : {_decode(msg.get('Subject'))}\n"
                f"Date    : {_decode(msg.get('Date'))}\n"
                f"Message-ID : {_decode(msg.get('Message-ID'))}\n"
                f"\n--- CORPS ---\n{corps[:4000]}"
                + ("\n[…tronqué…]" if len(corps) > 4000 else "")
            )
    except Exception as e:
        return f"Erreur lecture email : {e}"


# ----------------------------------------------------------------------
# Envoi (SMTP)
# ----------------------------------------------------------------------
def envoyer_email(
    provider: str,
    destinataire: str,
    sujet: str,
    corps: str,
    cc: str = "",
) -> str:
    """Envoie un email via SMTP."""
    try:
        addr, pwd, cfg = _get_credentials(provider)
        msg = EmailMessage()
        msg["From"] = addr
        msg["To"] = destinataire
        if cc:
            msg["Cc"] = cc
        msg["Subject"] = sujet
        msg.set_content(corps)

        ctx = ssl.create_default_context()
        with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"]) as smtp:
            smtp.starttls(context=ctx)
            smtp.login(addr, pwd)
            smtp.send_message(msg)
        return f"Email envoyé avec succès à {destinataire} via {provider}."
    except Exception as e:
        return f"Erreur envoi email : {e}"


# ----------------------------------------------------------------------
# Brouillons (IMAP APPEND) — recommandé pour valider avant envoi
# ----------------------------------------------------------------------
def creer_brouillon(
    provider: str,
    destinataire: str,
    sujet: str,
    corps: str,
) -> str:
    """Enregistre un brouillon dans le dossier Brouillons (à valider/envoyer manuellement)."""
    try:
        addr, pwd, cfg = _get_credentials(provider)
        msg = EmailMessage()
        msg["From"] = addr
        msg["To"] = destinataire
        msg["Subject"] = sujet
        msg["Date"] = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
        msg.set_content(corps)

        with imaplib.IMAP4_SSL(cfg["imap_host"], cfg["imap_port"]) as imap:
            imap.login(addr, pwd)
            res = imap.append(
                cfg["drafts_folder"],
                "\\Draft",
                imaplib.Time2Internaldate(time()),
                msg.as_bytes(),
            )
            if res[0] != "OK":
                return f"Échec création brouillon : {res}"
        return (
            f"Brouillon enregistré dans {cfg['drafts_folder']} ({provider}). "
            f"Va dans ta boîte mail pour le relire avant envoi."
        )
    except Exception as e:
        return f"Erreur création brouillon : {e}"
