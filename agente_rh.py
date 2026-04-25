"""
Agente Virtuelle RH - Orchestrateur principal
==============================================
Une agente RH propulsée par Claude (Anthropic) qui peut :
  - Répondre aux emails RH
  - Traiter les données employés
  - Pré-screener des CV
  - Générer des documents RH (attestations, lettres)
  - Répondre aux questions sur la politique de l'entreprise

Usage :
    python agente_rh.py                  # Mode chat interactif
    python agente_rh.py --demo           # Lance une démonstration
"""

import os
import sys
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

# Import des outils RH
from outils.email_handler import repondre_email
from outils.data_processor import (
    statistiques_employes,
    rechercher_employe,
    calculer_conges_restants,
)
from outils.screening_cv import screener_cv
from outils.contrat_generator import generer_document_rh
from outils.faq_rh import consulter_politique_rh
from outils.email_connector import (
    lire_emails_recents,
    lire_email,
    envoyer_email,
    creer_brouillon,
)
from outils.salary_calculator import simuler_salaire
from outils.rappels_rh import lister_rappels, prochains_anniversaires
from outils.facturation import (
    creer_facture,
    lister_factures,
    marquer_facture_payee,
    generer_relance,
    creer_client,
    lister_clients,
    modifier_client,
    supprimer_client,
)
from outils.exports import (
    exporter_facture_pdf,
    exporter_attestation_pdf,
    exporter_attestation_docx,
    exporter_employes_xlsx,
    exporter_factures_xlsx,
)

# Charger les variables d'environnement (clé API)
load_dotenv()

# ----------------------------------------------------------------------
# Configuration de l'agente
# ----------------------------------------------------------------------
MODEL = "claude-sonnet-4-5"  # modèle utilisé
MAX_TOKENS = 4096

# ----------------------------------------------------------------------
# Système bilingue FR / DE — la langue est choisie au démarrage via .env
# ----------------------------------------------------------------------
LANGUE = (os.getenv("LANGUE") or "FR").upper()
if LANGUE not in ("FR", "DE"):
    LANGUE = "FR"

SYSTEM_PROMPTS = {
    "FR": """Tu es Léa, une assistante virtuelle RH bienveillante, professionnelle et précise.
Tu travailles pour une entreprise SUISSE et tu réponds EN FRANÇAIS.

Contexte suisse :
- Salaires en CHF, souvent versés en 13 mois.
- 26 cantons, droit du travail = Code des Obligations (CO).
- Cotisations sociales : AVS, AI, APG, AC, LAA, LPP.
- Multilingue : la Suisse a 4 langues officielles (mais ici, tu parles français).

Ton rôle :
- Répondre aux questions des employés (vacances, paie, politique, etc.)
- Traiter les emails reçus par le service RH
- Aider au screening de candidats
- Générer des documents administratifs
- Analyser les données du personnel
- Simuler des calculs de salaire brut → net

Règles importantes :
1. Utilise les outils mis à ta disposition pour aller chercher des informations fiables.
2. Ne JAMAIS inventer une donnée chiffrée (salaire, ancienneté, solde de vacances). Si tu n'as pas l'info, utilise un outil ou demande.
3. Reste empathique mais factuelle. Le ton est tutoiement professionnel (vouvoiement si l'utilisateur vouvoie).
4. Pour toute demande sensible (licenciement, conflit, harcèlement), rappelle que la décision finale revient au DRH humain.
5. Pour les fiches de paie / calculs salariaux : précise toujours qu'il s'agit d'une SIMULATION INDICATIVE, à valider par fiduciaire.

RÈGLES SPÉCIALES POUR LES EMAILS :
- Pour LIRE les emails, utilise lire_emails_recents puis lire_email.
- Par défaut, NE JAMAIS envoyer un email directement : enregistre toujours un BROUILLON (creer_brouillon).
- N'utilise envoyer_email QUE si l'utilisateur l'a explicitement demandé.
""",
    "DE": """Du bist Lea, eine freundliche, professionelle und präzise virtuelle HR-Assistentin.
Du arbeitest für ein SCHWEIZER Unternehmen und antwortest AUF DEUTSCH.

Schweizer Kontext:
- Löhne in CHF, oft 13 Monatsgehälter.
- 26 Kantone, Arbeitsrecht = Obligationenrecht (OR).
- Sozialabgaben: AHV, IV, EO, ALV, UVG, BVG.
- Mehrsprachigkeit: Schweiz hat 4 Amtssprachen (aber hier sprichst du Deutsch).

Deine Aufgaben:
- Fragen von Mitarbeitenden beantworten (Ferien, Lohn, Richtlinien usw.)
- E-Mails der HR-Abteilung bearbeiten
- Bewerber-Screening unterstützen
- Verwaltungsdokumente erstellen
- Personaldaten analysieren
- Brutto/Netto-Lohnsimulationen durchführen

Wichtige Regeln:
1. Nutze die verfügbaren Tools, um zuverlässige Informationen zu erhalten.
2. Erfinde NIE Zahlen (Lohn, Dienstalter, Feriensaldo). Wenn du es nicht weisst, nutze ein Tool oder frage nach.
3. Bleibe empathisch und sachlich. Du-Form professionell (Sie-Form falls der Benutzer siezt).
4. Bei sensiblen Themen (Kündigung, Konflikt, Belästigung) verweise immer auf die menschliche HR-Leitung.
5. Bei Lohnabrechnungen: weise immer darauf hin, dass es sich um eine INDIKATIVE SIMULATION handelt, die von einem Treuhänder zu validieren ist.

SPEZIALREGELN FÜR E-MAILS:
- Zum LESEN: nutze lire_emails_recents, dann lire_email.
- Standardmässig NIEMALS direkt versenden: speichere immer einen ENTWURF (creer_brouillon).
- Nutze envoyer_email NUR auf ausdrücklichen Wunsch des Benutzers.
""",
}

SYSTEM_PROMPT = SYSTEM_PROMPTS[LANGUE]

# ----------------------------------------------------------------------
# Définition des outils que l'agente peut utiliser (tool use)
# ----------------------------------------------------------------------
TOOLS = [
    {
        "name": "repondre_email",
        "description": "Génère une réponse professionnelle à un email RH reçu. À utiliser quand l'utilisateur fournit un email entrant à traiter.",
        "input_schema": {
            "type": "object",
            "properties": {
                "email_recu": {
                    "type": "string",
                    "description": "Le contenu de l'email reçu auquel répondre",
                },
                "contexte": {
                    "type": "string",
                    "description": "Contexte additionnel optionnel (urgence, relation avec l'expéditeur)",
                },
            },
            "required": ["email_recu"],
        },
    },
    {
        "name": "statistiques_employes",
        "description": "Calcule des statistiques sur la base des employés (effectif, répartition par service, ancienneté moyenne, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "metrique": {
                    "type": "string",
                    "enum": ["effectif", "par_service", "anciennete", "masse_salariale", "tout"],
                    "description": "La statistique à calculer",
                }
            },
            "required": ["metrique"],
        },
    },
    {
        "name": "rechercher_employe",
        "description": "Recherche les informations d'un employé par nom ou matricule.",
        "input_schema": {
            "type": "object",
            "properties": {
                "requete": {
                    "type": "string",
                    "description": "Nom, prénom ou matricule de l'employé",
                }
            },
            "required": ["requete"],
        },
    },
    {
        "name": "calculer_conges_restants",
        "description": "Calcule le solde de congés restants d'un employé.",
        "input_schema": {
            "type": "object",
            "properties": {
                "matricule": {
                    "type": "string",
                    "description": "Matricule de l'employé (ex: EMP001)",
                }
            },
            "required": ["matricule"],
        },
    },
    {
        "name": "screener_cv",
        "description": "Évalue la pertinence d'un CV par rapport à une fiche de poste. Renvoie un score et une analyse.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cv_texte": {
                    "type": "string",
                    "description": "Le texte du CV du candidat",
                },
                "fiche_poste": {
                    "type": "string",
                    "description": "La fiche de poste / les exigences",
                },
            },
            "required": ["cv_texte", "fiche_poste"],
        },
    },
    {
        "name": "generer_document_rh",
        "description": "Génère un document RH officiel (attestation de travail, lettre, certificat).",
        "input_schema": {
            "type": "object",
            "properties": {
                "type_document": {
                    "type": "string",
                    "enum": ["attestation_travail", "attestation_salaire", "certificat_travail", "lettre_promotion"],
                    "description": "Le type de document à générer",
                },
                "matricule": {
                    "type": "string",
                    "description": "Matricule de l'employé concerné",
                },
                "details": {
                    "type": "string",
                    "description": "Détails additionnels (motif, destinataire, etc.)",
                },
            },
            "required": ["type_document", "matricule"],
        },
    },
    {
        "name": "consulter_politique_rh",
        "description": "Consulte la base de connaissances de l'entreprise (politique RH, congés, télétravail, code de conduite).",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "La question sur la politique de l'entreprise",
                }
            },
            "required": ["question"],
        },
    },
    # ------------------------------------------------------------------
    # Outils EMAIL (Gmail + Outlook via IMAP/SMTP)
    # ------------------------------------------------------------------
    {
        "name": "lire_emails_recents",
        "description": "Liste les N derniers emails de la boîte (Gmail ou Outlook). Renvoie l'ID, l'expéditeur, l'objet et la date.",
        "input_schema": {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "enum": ["gmail", "outlook"],
                    "description": "Le fournisseur de mail à interroger",
                },
                "limite": {
                    "type": "integer",
                    "description": "Nombre d'emails à lister (max 50)",
                    "default": 5,
                },
                "dossier": {
                    "type": "string",
                    "description": "Dossier IMAP (par défaut INBOX)",
                    "default": "INBOX",
                },
            },
            "required": ["provider"],
        },
    },
    {
        "name": "lire_email",
        "description": "Récupère le contenu complet d'un email spécifique par son ID (obtenu via lire_emails_recents).",
        "input_schema": {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "enum": ["gmail", "outlook"],
                },
                "message_id": {
                    "type": "string",
                    "description": "L'ID de l'email à lire",
                },
            },
            "required": ["provider", "message_id"],
        },
    },
    {
        "name": "creer_brouillon",
        "description": "Enregistre un brouillon d'email dans la boîte (à valider et envoyer manuellement par l'humain). MODE PAR DÉFAUT et recommandé.",
        "input_schema": {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "enum": ["gmail", "outlook"],
                },
                "destinataire": {
                    "type": "string",
                    "description": "Adresse email du destinataire",
                },
                "sujet": {
                    "type": "string",
                    "description": "Objet de l'email",
                },
                "corps": {
                    "type": "string",
                    "description": "Corps complet de l'email",
                },
            },
            "required": ["provider", "destinataire", "sujet", "corps"],
        },
    },
    # ------------------------------------------------------------------
    # Outil PAIE — simulation salaire suisse
    # ------------------------------------------------------------------
    {
        "name": "simuler_salaire",
        "description": "Simule la décomposition d'un salaire suisse brut → net (AVS, AI, APG, AC, LAA, LPP). Multi-cantons. Indique le salaire net mensuel et annuel. Renseigner age OU date_naissance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "salaire_brut_mensuel": {
                    "type": "number",
                    "description": "Salaire brut mensuel en CHF",
                },
                "canton": {
                    "type": "string",
                    "description": "Code canton (VD, GE, ZH, BE, etc.)",
                    "default": "VD",
                },
                "age": {
                    "type": "integer",
                    "description": "Âge de l'employé (utilisé pour calculer la LPP)",
                    "default": 35,
                },
                "treizieme": {
                    "type": "boolean",
                    "description": "True si 13e mois, sinon 12 mois",
                    "default": True,
                },
                "date_naissance": {
                    "type": "string",
                    "description": "Date de naissance YYYY-MM-DD (calcule l'âge automatiquement, prioritaire sur 'age')",
                },
            },
            "required": ["salaire_brut_mensuel"],
        },
    },
    # ------------------------------------------------------------------
    # Outils RAPPELS RH
    # ------------------------------------------------------------------
    {
        "name": "lister_rappels",
        "description": "Liste tous les rappels RH des N prochains jours : fins de période d'essai, anniversaires d'embauche (1/5/10/15/20 ans), échéances CDD, évaluations annuelles.",
        "input_schema": {
            "type": "object",
            "properties": {
                "jours_a_venir": {
                    "type": "integer",
                    "description": "Nombre de jours à scanner dans le futur (défaut 30)",
                    "default": 30,
                },
            },
        },
    },
    {
        "name": "prochains_anniversaires",
        "description": "Liste les anniversaires d'embauche significatifs (1, 5, 10, 15, 20 ans) à venir.",
        "input_schema": {
            "type": "object",
            "properties": {
                "jours": {"type": "integer", "default": 90},
            },
        },
    },
    # ------------------------------------------------------------------
    # Outils CLIENTS (CRUD)
    # ------------------------------------------------------------------
    {
        "name": "creer_client",
        "description": "Ajoute un nouveau client à la base. Le nom et l'email sont obligatoires. L'ID est généré automatiquement (CLI001, CLI002, …).",
        "input_schema": {
            "type": "object",
            "properties": {
                "nom": {"type": "string", "description": "Nom de l'entreprise (obligatoire)"},
                "email": {"type": "string", "description": "Email de contact principal (obligatoire)"},
                "contact": {"type": "string", "description": "Personne de contact (M. Dupont, Mme Martin…)"},
                "telephone": {"type": "string", "description": "Numéro de téléphone"},
                "adresse": {"type": "string", "description": "Adresse postale"},
                "npa": {"type": "string", "description": "Code postal (NPA en Suisse)"},
                "ville": {"type": "string", "description": "Ville"},
                "pays": {"type": "string", "description": "Code pays (CH par défaut)", "default": "CH"},
                "no_tva": {"type": "string", "description": "N° TVA (CHE-XXX.XXX.XXX en Suisse)"},
            },
            "required": ["nom", "email"],
        },
    },
    {
        "name": "lister_clients",
        "description": "Liste tous les clients enregistrés avec leurs coordonnées.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "modifier_client",
        "description": "Modifie un champ d'un client existant. Champs : nom, contact, email, telephone, adresse, npa, ville, pays, no_tva.",
        "input_schema": {
            "type": "object",
            "properties": {
                "id_client": {"type": "string", "description": "ID du client (CLI001, …)"},
                "champ": {"type": "string", "description": "Champ à modifier"},
                "nouvelle_valeur": {"type": "string", "description": "Nouvelle valeur du champ"},
            },
            "required": ["id_client", "champ", "nouvelle_valeur"],
        },
    },
    {
        "name": "supprimer_client",
        "description": "Supprime un client (refuse si des factures existent — conservation légale 10 ans en CH).",
        "input_schema": {
            "type": "object",
            "properties": {
                "id_client": {"type": "string"},
            },
            "required": ["id_client"],
        },
    },
    # ------------------------------------------------------------------
    # Outils FACTURATION (TVA suisse)
    # ------------------------------------------------------------------
    {
        "name": "creer_facture",
        "description": "Crée une nouvelle facture pour un client suisse (TVA appliquée). Génère le document texte et l'enregistre.",
        "input_schema": {
            "type": "object",
            "properties": {
                "id_client": {
                    "type": "string",
                    "description": "ID client (ex: CLI001) — utiliser lister_factures pour vérifier les clients existants",
                },
                "montant_ht": {"type": "number", "description": "Montant hors taxes en CHF"},
                "description": {"type": "string", "description": "Description de la prestation"},
                "taux_tva": {
                    "type": "number",
                    "description": "Taux TVA suisse : 8.1 (normal), 2.6 (alimentaire/livres), 3.8 (hôtellerie), 0 (exonéré)",
                    "default": 8.1,
                },
                "date_emission": {
                    "type": "string",
                    "description": "Date d'émission YYYY-MM-DD (défaut : aujourd'hui)",
                },
                "delai_paiement_jours": {
                    "type": "integer",
                    "description": "Délai de paiement en jours (défaut 30)",
                    "default": 30,
                },
            },
            "required": ["id_client", "montant_ht", "description"],
        },
    },
    {
        "name": "lister_factures",
        "description": "Liste les factures par statut : 'impayee' (par défaut), 'payee', 'retard' (impayées et échues), 'tout'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "statut": {
                    "type": "string",
                    "enum": ["impayee", "payee", "retard", "tout"],
                    "default": "impayee",
                },
            },
        },
    },
    {
        "name": "marquer_facture_payee",
        "description": "Marque une facture comme payée (encaissement reçu).",
        "input_schema": {
            "type": "object",
            "properties": {
                "numero": {"type": "string", "description": "Numéro de facture (ex: FA-2026-001)"},
                "date_paiement": {
                    "type": "string",
                    "description": "Date du paiement YYYY-MM-DD (défaut : aujourd'hui)",
                },
            },
            "required": ["numero"],
        },
    },
    {
        "name": "generer_relance",
        "description": "Génère un texte de relance pour une facture impayée. 3 niveaux : 1 (amical), 2 (ferme), 3 (mise en demeure formelle, art. 102 CO).",
        "input_schema": {
            "type": "object",
            "properties": {
                "numero": {"type": "string", "description": "Numéro de facture"},
                "niveau": {
                    "type": "integer",
                    "enum": [1, 2, 3],
                    "description": "1=amical, 2=ferme, 3=mise en demeure",
                    "default": 1,
                },
            },
            "required": ["numero"],
        },
    },
    # ------------------------------------------------------------------
    # Outils EXPORTS — fichiers téléchargeables
    # ------------------------------------------------------------------
    {
        "name": "exporter_facture_pdf",
        "description": "Génère un PDF officiel d'une facture existante (prêt à envoyer au client). Utilise quand l'utilisateur demande un PDF, un document à envoyer, à imprimer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "numero": {"type": "string", "description": "Numéro de facture (ex: FA-2026-001)"},
            },
            "required": ["numero"],
        },
    },
    {
        "name": "exporter_attestation_pdf",
        "description": "Génère un PDF d'attestation de travail pour un employé (signé par le DRH).",
        "input_schema": {
            "type": "object",
            "properties": {
                "matricule": {"type": "string", "description": "Matricule employé (ex: EMP001)"},
                "motif": {"type": "string", "description": "Motif de la demande (bail, banque, etc.)"},
            },
            "required": ["matricule"],
        },
    },
    {
        "name": "exporter_attestation_docx",
        "description": "Génère une attestation de travail au format Word (modifiable). À utiliser quand l'utilisateur veut éditer le document avant impression.",
        "input_schema": {
            "type": "object",
            "properties": {
                "matricule": {"type": "string"},
                "motif": {"type": "string"},
            },
            "required": ["matricule"],
        },
    },
    {
        "name": "exporter_employes_xlsx",
        "description": "Exporte la liste complète des employés au format Excel (.xlsx) avec mise en forme.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "exporter_factures_xlsx",
        "description": "Exporte les factures au format Excel avec totaux. Filtrer par statut si besoin.",
        "input_schema": {
            "type": "object",
            "properties": {
                "statut": {
                    "type": "string",
                    "enum": ["tout", "impayee", "payee"],
                    "default": "tout",
                },
            },
        },
    },
    {
        "name": "envoyer_email",
        "description": "Envoie DIRECTEMENT un email via SMTP. À UTILISER UNIQUEMENT si l'utilisateur a explicitement demandé l'envoi direct (sans validation manuelle). Sinon utiliser creer_brouillon.",
        "input_schema": {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "string",
                    "enum": ["gmail", "outlook"],
                },
                "destinataire": {
                    "type": "string",
                },
                "sujet": {
                    "type": "string",
                },
                "corps": {
                    "type": "string",
                },
                "cc": {
                    "type": "string",
                    "description": "Adresses en copie (optionnel)",
                },
            },
            "required": ["provider", "destinataire", "sujet", "corps"],
        },
    },
]

# Mapping nom outil -> fonction Python
OUTILS_DISPO = {
    "repondre_email": repondre_email,
    "statistiques_employes": statistiques_employes,
    "rechercher_employe": rechercher_employe,
    "calculer_conges_restants": calculer_conges_restants,
    "screener_cv": screener_cv,
    "generer_document_rh": generer_document_rh,
    "consulter_politique_rh": consulter_politique_rh,
    "lire_emails_recents": lire_emails_recents,
    "lire_email": lire_email,
    "creer_brouillon": creer_brouillon,
    "envoyer_email": envoyer_email,
    "simuler_salaire": simuler_salaire,
    "lister_rappels": lister_rappels,
    "prochains_anniversaires": prochains_anniversaires,
    "creer_facture": creer_facture,
    "lister_factures": lister_factures,
    "marquer_facture_payee": marquer_facture_payee,
    "generer_relance": generer_relance,
    "exporter_facture_pdf": exporter_facture_pdf,
    "exporter_attestation_pdf": exporter_attestation_pdf,
    "exporter_attestation_docx": exporter_attestation_docx,
    "exporter_employes_xlsx": exporter_employes_xlsx,
    "exporter_factures_xlsx": exporter_factures_xlsx,
    "creer_client": creer_client,
    "lister_clients": lister_clients,
    "modifier_client": modifier_client,
    "supprimer_client": supprimer_client,
}


# ----------------------------------------------------------------------
# Boucle agentique
# ----------------------------------------------------------------------
class AgenteRH:
    def __init__(self, langue: str = None):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("\nErreur : la variable ANTHROPIC_API_KEY n'est pas définie.")
            print("Crée un fichier .env à partir de .env.example et ajoute ta clé.\n")
            sys.exit(1)
        self.client = Anthropic(api_key=api_key)
        self.historique = []
        # Langue : passée en paramètre, sinon variable d'env, sinon FR
        lang = (langue or os.getenv("LANGUE") or "FR").upper()
        self.langue = lang if lang in ("FR", "DE") else "FR"
        self.system_prompt = SYSTEM_PROMPTS[self.langue]
        # Pour l'UI : tracer les outils utilisés au dernier tour
        self.dernier_outils_utilises: list[str] = []

    def executer_outil(self, nom_outil: str, parametres: dict) -> str:
        """Exécute un outil RH et retourne le résultat sous forme de texte."""
        if nom_outil not in OUTILS_DISPO:
            return f"Outil inconnu : {nom_outil}"
        try:
            resultat = OUTILS_DISPO[nom_outil](**parametres)
            if not isinstance(resultat, str):
                resultat = json.dumps(resultat, ensure_ascii=False, indent=2)
            return resultat
        except Exception as e:
            return f"Erreur lors de l'exécution de {nom_outil} : {e}"

    def chat(self, message_utilisateur: str, verbose: bool = True) -> str:
        """Une itération de l'agente : envoi message, gestion des outils, retour réponse.

        Args:
            message_utilisateur : message de l'utilisateur.
            verbose : si True, affiche dans le terminal les outils utilisés.
        """
        self.historique.append({"role": "user", "content": message_utilisateur})
        self.dernier_outils_utilises = []

        # Boucle agentique : tant que Claude veut utiliser des outils, on les exécute
        while True:
            reponse = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=self.system_prompt,
                tools=TOOLS,
                messages=self.historique,
            )

            # Si Claude veut utiliser un ou plusieurs outils
            if reponse.stop_reason == "tool_use":
                self.historique.append({"role": "assistant", "content": reponse.content})
                resultats_outils = []
                for bloc in reponse.content:
                    if bloc.type == "tool_use":
                        if verbose:
                            print(f"  [Léa utilise l'outil : {bloc.name}]")
                        self.dernier_outils_utilises.append(bloc.name)
                        sortie = self.executer_outil(bloc.name, bloc.input)
                        resultats_outils.append({
                            "type": "tool_result",
                            "tool_use_id": bloc.id,
                            "content": sortie,
                        })
                self.historique.append({"role": "user", "content": resultats_outils})
                continue

            # Sinon, réponse finale en texte
            texte_final = ""
            for bloc in reponse.content:
                if bloc.type == "text":
                    texte_final += bloc.text
            self.historique.append({"role": "assistant", "content": reponse.content})
            return texte_final


# ----------------------------------------------------------------------
# Mode interactif (chat)
# ----------------------------------------------------------------------
def mode_chat():
    bannieres = {
        "FR": (
            "  Agente Virtuelle RH (Suisse) - Léa",
            "  Langue : FR | Tape 'quitter' pour sortir, 'reset' pour effacer l'historique",
        ),
        "DE": (
            "  Virtuelle HR-Assistentin (Schweiz) - Lea",
            "  Sprache: DE | 'quitter' zum Beenden, 'reset' zum Zurücksetzen",
        ),
    }
    titre, sous_titre = bannieres[LANGUE]
    print("=" * 60)
    print(titre)
    print(sous_titre)
    print("=" * 60)
    agente = AgenteRH()
    while True:
        try:
            entree = input("\nToi  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nÀ bientôt !")
            break
        if not entree:
            continue
        if entree.lower() in ("quitter", "exit", "quit", "q"):
            print("À bientôt !")
            break
        if entree.lower() == "reset":
            agente.historique = []
            print("[historique effacé]")
            continue
        try:
            reponse = agente.chat(entree)
            print(f"\nLéa  > {reponse}")
        except Exception as e:
            print(f"\n[Erreur] {e}")


# ----------------------------------------------------------------------
# Mode démo
# ----------------------------------------------------------------------
def mode_demo():
    print("=== DÉMONSTRATION ===\n")
    agente = AgenteRH()
    exemples = [
        "Bonjour Léa, peux-tu me donner les statistiques de l'effectif par service ?",
        "Combien de jours de congés reste-t-il à l'employé EMP002 ?",
        "Quelle est notre politique de télétravail ?",
        ("Réponds à cet email reçu : "
         "'Bonjour, je souhaiterais poser 2 semaines de vacances en août. "
         "Comment dois-je procéder ? Merci, Sophie'"),
    ]
    for q in exemples:
        print(f"\n>>> {q}")
        rep = agente.chat(q)
        print(f"\nLéa : {rep}\n")
        print("-" * 60)


# ----------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agente Virtuelle RH (Léa)")
    parser.add_argument("--demo", action="store_true", help="Lancer une démo")
    args = parser.parse_args()
    if args.demo:
        mode_demo()
    else:
        mode_chat()
