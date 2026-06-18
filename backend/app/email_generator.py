import os
import sys
import json
import time
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import pandas as pd

load_dotenv()

DATABASE_URL       = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql+psycopg2://").replace("postgresql://", "postgresql+psycopg2://")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
BREVO_API_KEY      = os.getenv("BREVO_API_KEY")
FROM_EMAIL         = os.getenv("FROM_EMAIL", "contact@leadpilot.tn")
FROM_NAME          = os.getenv("FROM_NAME", "LeadPilot")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('email_generator.log', encoding='utf-8')
    ]
)
logger = logging.getLogger("leadpilot.email_generator")

# MODÈLES OPENROUTER GRATUITS
OPENROUTER_MODELS = [
    "nvidia/llama-3.1-nemotron-ultra-253b-v1:free",
    "openai/gpt-oss-120b:free",
    "openai/gpt-oss-20b:free",
    "google/gemma-4-31b-it:free",
    "z-ai/glm-4.5-air:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
]

# PROMPTS PAR SEGMENT
SEGMENT_PROMPTS = {
    "Chaud":  {
        "subject_hint": "proposition de valeur directe et urgente",
        "tone": "direct, confiant, orienté ROI",
        "cta": "Planifier un appel de 15 minutes cette semaine",
        "context": "Ce prospect est chaud : profil complet, joignable, score élevé. Email de prospection direct.",
    },
    "Prêts à Acheter": {
        "subject_hint": "contenu utile ou ressource gratuite",
        "tone": "éducatif, empathique, sans pression",
        "cta": "Télécharger notre guide gratuit ou répondre à cet email",
        "context": "Ce prospect est prêt à acheter : l'intéresser avec de la valeur avant de vendre. Email nurturing.",
    },
    "Froid": {
        "subject_hint": "question ouverte ou statistique surprenante du secteur",
        "tone": "curieux, léger, non commercial",
        "cta": "Juste répondre OUI ou NON à cette question",
        "context": "Ce prospect est froid : objectif = obtenir une réponse, pas vendre. Email très court.",
    },
    "À Risque": {
        "subject_hint": "offre de diagnostic gratuit ou audit rapide",
        "tone": "utile, sans engagement, rassurant",
        "cta": "Audit gratuit de 30 minutes sans engagement",
        "context": "Ce prospect a un profil incomplet. Proposer quelque chose de gratuit pour le qualifier.",
    },
}

# PROMPTS PAR SECTEUR
SECTOR_PROMPTS = {
    "Informatique & Tech": {
        "angle": "automatisation des processus de vente et gain de temps développeur",
        "pain_point": "trop de temps perdu sur la prospection manuelle, pipeline mal qualifié",
        "value_prop": "LeadPilot identifie et contacte automatiquement vos meilleurs prospects B2B",
        "vocabulary": "utilise des termes tech : pipeline, automation, API, ROI, conversion rate",
        "tone_extra": "parle tech-to-tech, sois direct et concis, évite le jargon commercial classique",
    },
    "Marketing & Communication": {
        "angle": "acquisition de nouveaux clients et optimisation des campagnes B2B",
        "pain_point": "difficulté à trouver des prospects B2B qualifiés pour leurs propres clients",
        "value_prop": "LeadPilot génère des leads B2B qualifiés avec scoring IA pour vos campagnes",
        "vocabulary": "utilise : leads qualifiés, taux de conversion, nurturing, funnel, campagne ciblée",
        "tone_extra": "montre que tu comprends le métier d'agence, parle résultats mesurables",
    },
    "Finance & Comptabilité": {
        "angle": "réduction du temps de prospection et amélioration du portefeuille clients",
        "pain_point": "développement commercial chronophage qui prend du temps sur le cœur de métier",
        "value_prop": "LeadPilot automatise l'acquisition de nouveaux clients PME pour les cabinets",
        "vocabulary": "utilise : portefeuille clients, prospection ciblée, cabinet, gestion de la relation client",
        "tone_extra": "sois formel et professionnel, mets en avant la fiabilité et les données chiffrées",
    },
    "Services aux entreprises": {
        "angle": "développement commercial B2B et fidélisation clients",
        "pain_point": "manque de visibilité sur les prospects les plus susceptibles de convertir",
        "value_prop": "LeadPilot priorise vos prospects B2B selon leur probabilité d'achat grâce à l'IA",
        "vocabulary": "utilise : prospects qualifiés, développement commercial, relation client, B2B",
        "tone_extra": "ton consultif, montre une compréhension des enjeux business de leur secteur",
    },
    "Immobilier": {
        "angle": "ciblage d'entreprises cherchant des locaux professionnels ou en expansion",
        "pain_point": "difficulté à identifier les entreprises en croissance ayant des besoins immobiliers",
        "value_prop": "LeadPilot identifie les PME et startups en phase de croissance = futurs clients",
        "vocabulary": "utilise : locaux professionnels, entreprises en croissance, portefeuille, transaction",
        "tone_extra": "sois précis sur les opportunités business, évite le ton promotionnel immobilier résidentiel",
    },
    "Construction & BTP": {
        "angle": "acquisition de contrats B2B et développement du carnet de commandes",
        "pain_point": "dépendance aux appels d'offres publics et difficulté à prospecter le privé",
        "value_prop": "LeadPilot identifie les entreprises ayant des projets de construction ou rénovation",
        "vocabulary": "utilise : carnet de commandes, maître d'ouvrage, appel d'offres, contrat",
        "tone_extra": "sois concret et orienté résultats, parle chiffre d'affaires et contrats",
    },
    "Transport & Logistique": {
        "angle": "développement de nouveaux partenariats B2B et contrats transport",
        "pain_point": "recherche de nouveaux chargeurs et partenaires commerciaux B2B",
        "value_prop": "LeadPilot identifie les entreprises ayant des besoins logistiques récurrents",
        "vocabulary": "utilise : chargeurs, fret, partenariat, contrat cadre, flux logistique",
        "tone_extra": "sois efficace et orienté service, mets en avant la fiabilité",
    },
    "Education & Formation": {
        "angle": "partenariats B2B avec des entreprises pour la formation continue",
        "pain_point": "difficulté à trouver des entreprises cherchant à former leurs équipes",
        "value_prop": "LeadPilot cible les PME et grandes entreprises avec des budgets formation",
        "vocabulary": "utilise : formation professionnelle, CPF, plan de développement des compétences",
        "tone_extra": "sois institutionnel et rassurant, met en avant la pédagogie et les certifications",
    },
}

DEFAULT_SECTOR_PROMPT = {
    "angle": "développement commercial et acquisition de nouveaux clients B2B",
    "pain_point": "temps perdu en prospection non qualifiée",
    "value_prop": "LeadPilot automatise votre prospection B2B avec l'intelligence artificielle",
    "vocabulary": "utilise un vocabulaire business professionnel",
    "tone_extra": "sois professionnel et orienté valeur",
}

# GÉNÉRATION EMAIL VIA OPENROUTER
SENDER_COMPANY = "LeadPilot"

def build_prompt(lead: dict, segment: str, version: str = "A",
                 user_subject: str = None, user_cta: str = None, user_tone: str = None) -> str:
    hints     = SEGMENT_PROMPTS.get(segment, SEGMENT_PROMPTS["Froid"])
    company   = lead.get("company") or "votre entreprise"
    sector    = lead.get("sector") or "votre secteur"
    region    = lead.get("region") or "Tunisie"
    ctype     = lead.get("company_type") or "entreprise"
    firstname = lead.get("first_name") or ""

    # Paramètres utilisateur ou fallback automatique par segment
    # Personnalisation prénom dans l'objet : +33% d'ouverture selon HubSpot
    firstname_hint = f" — si possible inclure le prénom '{firstname}' dans l'objet" if firstname else ""
    subject_instruction = (
        f"Utilise EXACTEMENT cet objet : \"{user_subject}\""
        if user_subject
        else f"Génère un objet accrocheur ({hints['subject_hint']}{firstname_hint})"
    )
    cta_instruction  = user_cta  or hints["cta"]
    tone_instruction = user_tone or hints["tone"]

    variation = ""
    if version == "B":
        variation = "Version B : reformule l'accroche différemment, varie le CTA, garde le même objet."

    # Personnalisation par secteur
    sp = SECTOR_PROMPTS.get(sector, DEFAULT_SECTOR_PROMPT)

    return f"""Tu es un expert en prospection B2B tunisien. Génère un email commercial personnalisé.

Données du prospect :
- Entreprise : {company}
- Secteur : {sector}
- Région : {region}
- Type d'entreprise : {ctype}
- Prénom contact : {firstname or 'Non disponible'}
- Segment CRM : {segment}

Contexte secteur ({sector}) — adapte TOUT ton email à ce contexte :
- Angle d'approche : {sp['angle']}
- Pain point typique de ce secteur : {sp['pain_point']}
- Proposition de valeur adaptée : {sp['value_prop']}
- Vocabulaire métier à utiliser : {sp['vocabulary']}
- Ton spécifique secteur : {sp['tone_extra']}

Consignes générales :
- Objet : {subject_instruction}
- Ton global : {tone_instruction}
- CTA (appel à l'action) : {cta_instruction}
- Contexte segment : {hints['context']}
- Longueur corps : 100-150 mots maximum
- Langue : français professionnel
- Tu représentes la société **LeadPilot** — utilise TOUJOURS ce nom exact
- INTERDIT d'écrire : [Votre Entreprise], [Votre Société], [Votre Prénom], [Nom], [Poste], [Téléphone], [Email], [lien], [URL]
- JAMAIS de lien, d'URL ou de lien de réservation dans l'email — utilise uniquement "Répondez à cet email"
- Termine TOUJOURS par cette signature exacte :
  Cordialement,
  L'équipe LeadPilot
  contact@leadpilot.tn | www.leadpilot.tn
- Personnalise avec le nom de l'entreprise ET son secteur spécifique
{variation}

Réponds UNIQUEMENT en JSON valide :
{{"subject": "...", "body": "..."}}"""


def generate_email_openrouter(lead: dict, segment: str, version: str = "A",
                               user_subject: str = None, user_cta: str = None, user_tone: str = None) -> dict:
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY manquante dans .env")
        return {}

    prompt = build_prompt(lead, segment, version, user_subject, user_cta, user_tone)

    for model in OPENROUTER_MODELS:
        try:
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://leadpilot.tn",
                    "X-Title": "LeadPilot",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 400,
                },
                timeout=25,
            )
            data = r.json()

            if "choices" not in data:
                err = data.get("error", {}).get("message", "?")
                logger.warning(f" {model}: {err}")
                continue

            content = data["choices"][0]["message"]["content"].strip()
            content = content.replace("```json", "").replace("```", "").strip()

            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                import re
                match = re.search(r'\{.*\}', content, re.DOTALL)
                if match:
                    result = json.loads(match.group(0))
                else:
                    continue

            if result.get("subject") and result.get("body"):
                logger.info(f"   {model} | v{version} | objet: {result['subject'][:50]}")
                return result

        except Exception as e:
            logger.error(f" {model} erreur: {e}")
            continue

    logger.error(" Tous les modèles OpenRouter épuisés")
    return {}


# ENVOI VIA BREVO
def send_email_brevo(to_email: str, to_name: str, subject: str, body: str, lead_id: int = None,
                     cta_text: str = None, cta_link: str = None) -> bool:
    if not BREVO_API_KEY:
        logger.warning(" BREVO_API_KEY manquante — envoi ignoré")
        return False

    from urllib.parse import quote
    base_url = os.environ.get("APP_BASE_URL", "http://127.0.0.1:8000")

    pixel = ""
    cta_button = ""
    if lead_id:
        pixel = f'<img src="{base_url}/campaigns/track/open?lead_id={lead_id}" width="1" height="1" style="display:none" alt=""/>'
        if cta_text:
            dest = cta_link or "https://leadpilot.io"
            tracked = f'{base_url}/campaigns/track/click?lead_id={lead_id}&url={quote(dest, safe="")}'
            cta_button = (
                f'<div style="margin:24px 0;">'
                f'<a href="{tracked}" style="display:inline-block;background:#6366f1;color:#fff;'
                f'text-decoration:none;font-weight:600;font-size:14px;padding:12px 24px;border-radius:8px;">'
                f'{cta_text}</a></div>'
            )

    try:
        r = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "api-key": BREVO_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "sender": {"name": FROM_NAME, "email": FROM_EMAIL},
                "to": [{"email": to_email, "name": to_name}],
                "subject": subject,
                "textContent": body,
                "htmlContent": f"<p>{body.replace(chr(10), '<br>')}</p>{cta_button}{pixel}",
            },
            timeout=15,
        )
        if r.status_code in (200, 201):
            logger.info(f" Envoyé à {to_email}")
            return True
        else:
            logger.error(f" Brevo erreur {r.status_code}: {r.text[:200]}")
            return False
    except Exception as e:
        logger.error(f" Brevo exception: {e}")
        return False


# SAUVEGARDE EMAIL EN BASE (colonnes email_sent_*)
def save_email_to_db(engine, lead_id: int, subject_a: str, body_a: str,
                     subject_b: str, body_b: str, sent: bool, ab_version: str = None):
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE leads SET
                email_subject_a  = :sa,
                email_body_a     = :ba,
                email_subject_b  = :sb,
                email_body_b     = :bb,
                email_sent       = :sent,
                email_sent_at    = :ts,
                ab_version       = :ab
            WHERE id = :id
        """), {
            "sa": subject_a, "ba": body_a,
            "sb": subject_b, "bb": body_b,
            "sent": sent,
            "ts": datetime.utcnow() if sent else None,
            "ab": ab_version,
            "id": lead_id,
        })
        conn.commit()


# PIPELINE PRINCIPAL
def generate_emails(segment: str = None, limit: int = 50, dry_run: bool = True,
                    user_subject: str = None, user_cta: str = None, user_tone: str = None,
                    sector: str = None, region: str = None, lead_ids: list = None,
                    regenerate: bool = False, user_cta_link: str = None):
    logger.info("=" * 55)
    logger.info("LeadPilot — Email Generator")
    logger.info(f"Segment : {segment or 'TOUS'} | Limite : {limit} | Dry-run : {dry_run}")
    logger.info(f"OpenRouter : {'' if OPENROUTER_API_KEY else ' '}")
    logger.info(f"Brevo      : {'' if BREVO_API_KEY else ' (dry-run forcé)'}")
    logger.info("=" * 55)

    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY manquante — arrêt")
        return

    engine = create_engine(DATABASE_URL)

    # Requête leads avec email
    where_clauses = ["email IS NOT NULL", "email != ''"]

    # Si des sociétés spécifiques sont sélectionnées ignorer les autres filtres
    if lead_ids:
        ids_str = ",".join(str(i) for i in lead_ids)
        where_clauses.append(f"id IN ({ids_str})")
    else:
        if segment:
            where_clauses.append(f"segment = '{segment}'")
        if sector:
            where_clauses.append(f"sector = '{sector}'")
        if region:
            where_clauses.append(f"region ILIKE '%{region}%'")

    # Si regenerate=True regénère même les leads déjà générés
    if not regenerate:
        where_clauses.append("(email_sent IS NULL OR email_sent = FALSE)")

    query = f"""
        SELECT id, company, first_name, last_name, email,
               sector, region, company_type, segment, lead_score
        FROM leads
        WHERE {' AND '.join(where_clauses)}
        ORDER BY lead_score DESC NULLS LAST
        LIMIT {limit}
    """

    df = pd.read_sql(query, engine)
    logger.info(f" {len(df)} leads à traiter")

    if len(df) == 0:
        logger.info("Aucun lead éligible.")
        return

    sent_count = generated_count = error_count = 0
    total = len(df)

    for idx, (_, row) in enumerate(df.iterrows()):
        lead = row.to_dict()
        seg  = lead.get("segment") or segment or "Froid"
        name = f"{lead.get('first_name') or ''} {lead.get('last_name') or ''}".strip() or lead.get("company") or "Contact"

        # A/B Testing 50/50 — indices pairs A, impairs B
        ab_version = "A" if idx % 2 == 0 else "B"

        logger.info(f"\n[{idx+1}/{total}] {lead.get('company')} | {seg} | v={ab_version} | score={lead.get('lead_score')}")

        # Générer les 2 versions
        email_a = generate_email_openrouter(lead, seg, version="A",
                    user_subject=user_subject, user_cta=user_cta, user_tone=user_tone)
        time.sleep(0.5)
        email_b = generate_email_openrouter(lead, seg, version="B",
                    user_subject=user_subject, user_cta=user_cta, user_tone=user_tone)
        time.sleep(0.5)

        if not email_a:
            error_count += 1
            continue

        generated_count += 1

        # Choisir la version à envoyer selon l'assignation A/B
        email_to_send = email_a if ab_version == "A" else (email_b or email_a)

        if dry_run:
            logger.info(f"   [DRY-RUN] Version assignée : {ab_version}")
            logger.info(f"   [DRY-RUN] Objet A : {email_a.get('subject')}")
            logger.info(f"   [DRY-RUN] Objet B : {email_b.get('subject') if email_b else 'N/A'}")
        else:
            sent = send_email_brevo(
                to_email=lead["email"],
                to_name=name,
                subject=email_to_send["subject"],
                body=email_to_send["body"],
                lead_id=int(lead["id"]),
                cta_text=user_cta or "En savoir plus",
                cta_link=user_cta_link,
            )
            if sent:
                sent_count += 1
                logger.info(f" Envoyé version {ab_version} à {lead['email']}")

        # Sauvegarder en base avec la version assignée
        try:
            save_email_to_db(
                engine=engine,
                lead_id=int(lead["id"]),
                subject_a=email_a.get("subject", ""),
                body_a=email_a.get("body", ""),
                subject_b=email_b.get("subject", "") if email_b else "",
                body_b=email_b.get("body", "") if email_b else "",
                sent=not dry_run,
                ab_version=ab_version,
            )
        except Exception as e:
            logger.warning(f" Sauvegarde DB échouée: {e}")

    logger.info(f"\n{'='*55}")
    logger.info(f"Terminé !")
    logger.info(f"   Générés  : {generated_count}")
    logger.info(f"   Envoyés  : {sent_count}")
    logger.info(f"   Erreurs  : {error_count}")
    if dry_run:
        logger.info("   Mode dry-run — aucun email envoyé")
    else:
        try:
            from app.routers.notifications import push_notification
            push_notification("camp", "Campagne terminée",
                f"{sent_count} emails envoyés · {generated_count} générés")
        except Exception as e:
            logger.error(f"[NOTIF] {e}")


# CLI
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="LeadPilot Email Generator")
    parser.add_argument("--segment", choices=["Chaud", "Prêts à Acheter", "Froid", "À Risque"],
                        help="Segment cible")
    parser.add_argument("--all", action="store_true", help="Tous les segments")
    parser.add_argument("--limit", type=int, default=50, help="Nombre max de leads")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Générer sans envoyer (défaut: True)")
    parser.add_argument("--send", action="store_true",
                        help="Envoyer réellement via Brevo (désactive dry-run)")
    args = parser.parse_args()

    dry = not args.send

    if args.all:
        for seg in ["Chaud", "Prêts à Acheter", "À Risque", "Froid"]:
            generate_emails(segment=seg, limit=args.limit // 4, dry_run=dry)
    else:
        generate_emails(segment=args.segment, limit=args.limit, dry_run=dry)
