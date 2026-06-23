from app.celery_app import celery_app
from app.database import SyncSessionLocal
from app.models.lead import Lead
from app.models.scraping_job import ScrapingJob
from sqlalchemy import text, func, case
import redis
import json
import re
import logging
from datetime import datetime, timedelta
from difflib import SequenceMatcher

logger = logging.getLogger("leadpilot.tasks")
r = redis.Redis(host='localhost', port=6379, db=0)

# UTILITAIRES ETL
def safe_int(val):
    try:
        return int(float(str(val).strip())) if val and str(val).strip() else None
    except (ValueError, TypeError):
        return None

def safe_float(val):
    try:
        return float(str(val).strip()) if val and str(val).strip() else None
    except (ValueError, TypeError):
        return None

def clean_name(name: str) -> str:
    if not name or str(name).strip() in ['', 'nan', 'None']:
        return None
    name = re.sub(r'[^\w\s\-\.\,\&\(\)\'\"àâäéèêëîïôùûüçÀÂÄÉÈÊËÎÏÔÙÛÜÇ]', ' ', str(name))
    name = re.sub(r'\s+', ' ', name).strip()
    return name.title() if name else None

def normalize_phone(phone: str) -> str:
    if not phone or str(phone).strip() in ['', 'nan', 'None']:
        return None
    digits = re.sub(r'[^\d]', '', str(phone))
    if digits.startswith('216') and len(digits) == 11:
        digits = digits[3:]
    if len(digits) == 8:
        return f"+216 {digits[:2]} {digits[2:5]} {digits[5:]}"
    return str(phone).strip() or None

def normalize_email(email: str) -> str:
    if not email or str(email).strip() in ['', 'nan', 'None']:
        return None
    email = str(email).strip().lower()
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    if re.match(pattern, email):
        blacklist = ['example', 'test', 'noreply', 'no-reply',
                     'donotreply', 'tunisieindex', 'wordpress']
        if not any(b in email for b in blacklist):
            return email
    return None

def normalize_website(website: str) -> str:
    if not website or str(website).strip() in ['', 'nan', 'None']:
        return None
    website = str(website).strip()
    if not website.startswith('http'):
        website = 'https://' + website
    return website.rstrip('/') or None

def extract_city(address: str, region: str) -> str:
    tunisian_cities = {
        'tunis': 'Tunis', 'sfax': 'Sfax', 'sousse': 'Sousse',
        'monastir': 'Monastir', 'bizerte': 'Bizerte', 'nabeul': 'Nabeul',
        'ariana': 'Ariana', 'ben arous': 'Ben Arous', 'gabes': 'Gabès',
        'medenine': 'Médenine', 'kairouan': 'Kairouan', 'gafsa': 'Gafsa',
        'beja': 'Béja', 'jendouba': 'Jendouba', 'mahdia': 'Mahdia',
        'manouba': 'Manouba', 'zaghouan': 'Zaghouan', 'siliana': 'Siliana',
        'kasserine': 'Kasserine', 'sidi bouzid': 'Sidi Bouzid',
        'tataouine': 'Tataouine', 'tozeur': 'Tozeur', 'kebili': 'Kébili',
        'kef': 'Kef', 'hammamet': 'Hammamet', 'msaken': 'Msaken',
    }
    for t in [address, region]:
        if t:
            for key, val in tunisian_cities.items():
                if key in str(t).lower():
                    return val
    return None


# DÉDUPLICATION AUTOMATIQUE
def _normalize_company_name(name: str) -> str:
    """Normalise un nom entreprise pour comparaison fuzzy."""
    if not name:
        return ""
    n = name.lower().strip()
    # Supprimer formes juridiques courantes
    for prefix in ["sarl ", "sa ", "sas ", "ste ", "société ", "company ", "co. ", "llc ", "inc. "]:
        n = n.replace(prefix, "")
    n = re.sub(r"[^\w\s]", "", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _fuzzy_similar(a: str, b: str, threshold: float = 0.85) -> bool:
    """Retourne True si les deux noms sont fuzzy-similaires (>= threshold)."""
    na, nb = _normalize_company_name(a), _normalize_company_name(b)
    if not na or not nb:
        return False
    return SequenceMatcher(None, na, nb).ratio() >= threshold


def deduplicate_leads():
    """
    1. Déduplication exacte SQL sur nom (insensible à la casse)
    2. Déduplication fuzzy Python sur les noms proches (ex: 'SARL Mahjoub' = 'Mahjoub SARL')
    Appelée automatiquement après process_leads_from_queue()
    """
    db = SyncSessionLocal()
    try:
        # Déduplication exacte rapide via SQL
        result = db.execute(text("""
            DELETE FROM leads a USING leads b
            WHERE a.id > b.id
            AND LOWER(a.company) = LOWER(b.company)
        """))
        db.commit()
        exact_deleted = result.rowcount
        print(f" Déduplication exacte : {exact_deleted} doublons supprimés")

        # Déduplication fuzzy : charger tous les noms récents (30 derniers jours)
        cutoff = datetime.utcnow() - timedelta(days=30)
        rows = db.execute(text(
            "SELECT id, company FROM leads WHERE company IS NOT NULL AND created_at > :c ORDER BY id",
        ), {"c": cutoff}).fetchall()

        ids_to_delete = set()
        seen = []  # liste (id, company)
        for row in rows:
            rid, rcompany = row.id, row.company
            if rid in ids_to_delete:
                continue
            for sid, scompany in seen:
                if _fuzzy_similar(rcompany, scompany):
                    ids_to_delete.add(rid)
                    break
            else:
                seen.append((rid, rcompany))

        fuzzy_deleted = 0
        if ids_to_delete:
            db.execute(text(f"DELETE FROM leads WHERE id IN ({','.join(str(i) for i in ids_to_delete)})"))
            db.commit()
            fuzzy_deleted = len(ids_to_delete)
            print(f" Déduplication fuzzy : {fuzzy_deleted} doublons supprimés")

        return exact_deleted + fuzzy_deleted
    except Exception as e:
        db.rollback()
        print(f" Erreur déduplication: {e}")
        return 0
    finally:
        db.close()


# TÂCHE CELERY PRINCIPALE — ETL
@celery_app.task
def process_leads_from_queue():
    db = SyncSessionLocal()
    processed = skipped = errors = 0

    while True:
        data = r.rpop('leads_queue')
        if not data:
            break

        try:
            raw_data = json.loads(data)

            # EXTRACTION
            raw_name    = raw_data.get('name') or raw_data.get('company') or ''
            raw_email   = raw_data.get('email') or ''
            raw_phone   = raw_data.get('phone_number') or raw_data.get('phone') or ''
            raw_website = raw_data.get('website') or ''
            raw_address = raw_data.get('address') or ''
            raw_sector  = raw_data.get('sector') or raw_data.get('place_type') or ''
            raw_region  = raw_data.get('region') or raw_data.get('city') or ''

            # TRANSFORMATION ETL
            name    = clean_name(raw_name)
            email   = normalize_email(raw_email)
            phone   = normalize_phone(raw_phone)
            website = normalize_website(raw_website)
            address = raw_address.strip() if raw_address and str(raw_address) not in ['nan', 'None'] else None
            sector  = raw_sector.strip() if raw_sector and str(raw_sector) not in ['nan', 'None'] else None
            city    = extract_city(address or '', raw_region)

            # Rejeter leads sans nom
            if not name:
                skipped += 1
                continue

            # DÉDUPLICATION PRÉ-INSERTION
            existing = None
            if email:
                existing = db.query(Lead).filter(func.lower(Lead.email) == email.lower()).first()
            if not existing and phone:
                existing = db.query(Lead).filter(Lead.phone == phone).first()
            if not existing and name:
                # Exact insensible à la casse
                existing = db.query(Lead).filter(func.lower(Lead.company) == name.lower()).first()
            if not existing and name:
                # Fuzzy : vérifier les noms proches parmi les 500 derniers leads
                recent = db.query(Lead.company).order_by(Lead.id.desc()).limit(500).all()
                for (rname,) in recent:
                    if rname and _fuzzy_similar(name, rname):
                        existing = True
                        break

            if existing:
                skipped += 1
                continue

            # INJECTION POSTGRESQL
            lead = Lead(
                company=name,
                email=email,
                phone=phone,
                job_title=raw_data.get('job_title') or None,
                address=address,
                website=website,
                sector=sector,
                region=city or (raw_region if raw_region and str(raw_region) not in ['nan', 'None'] else None),
                reviews_count=safe_int(raw_data.get('reviews_count')),
                reviews_average=safe_float(raw_data.get('reviews_average')),
                scraping_url=raw_data.get('scraping_url') or raw_data.get('url') or None,
                source=raw_data.get('source', 'scraping'),
                score_fiabilite=0.0,
                status='new',
                enriched=False,
            )

            db.add(lead)
            processed += 1

            if processed % 100 == 0:
                db.commit()
                print(f" {processed} leads insérés...")

        except Exception as e:
            errors += 1
            print(f" Erreur: {e}")
            continue

    db.commit()
    db.close()

    # Déduplication automatique après insertion
    deduplicate_leads()

    print(f"\nETL terminé !")
    print(f"   Insérés  : {processed}")
    print(f"   Ignorés  : {skipped}")
    print(f"   Erreurs  : {errors}")
    return {"processed": processed, "skipped": skipped, "errors": errors}


# TÂCHE SCRAPING — OVERPASS API (OPENSTREETMAP)
@celery_app.task(name="app.tasks.run_scraping_job")
def run_scraping_job(job_id: int):
    """
    Exécute un job de scraping via Overpass API (OpenStreetMap).
    Met à jour le statut du job et insère les leads en base.
    """
    db = SyncSessionLocal()
    try:
        # 1. Charger le job
        job = db.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
        if not job:
            logger.error(f"[SCRAPING] Job {job_id} introuvable")
            return

        # 2. Passer en actif
        job.status     = "actif"
        job.started_at = datetime.utcnow()
        db.commit()
        logger.info(f"[SCRAPING] Job {job_id} démarré : {job.name}")

        # 3. Lancer le scraper selon la source
        from app.scraper import run_scraper
        raw_leads = run_scraper(
            source    = job.source    or "Google Maps",
            keywords  = job.keywords  or "",
            location  = job.location  or "",
            sector    = job.sector    or "",
            max_leads = job.max_leads or 50,
        )
        logger.info(f"[SCRAPING] {len(raw_leads)} leads trouvés pour job {job_id}")

        # 4. Insérer les leads (avec déduplication par company)
        inserted = 0
        new_leads_objs = []
        for raw in raw_leads:
            name = raw.get("company", "").strip()
            if not name:
                continue
            existing = db.query(Lead).filter(Lead.company == name).first()
            if existing:
                continue
            lead = Lead(
                company          = name,
                email            = normalize_email(raw.get("email") or ""),
                phone            = raw.get("phone"),
                website          = raw.get("website"),
                address          = raw.get("address"),
                region           = raw.get("region"),
                sector           = raw.get("sector"),
                reviews_count    = raw.get("reviews_count"),
                reviews_average  = raw.get("reviews_average"),
                source           = raw.get("source", "scraping"),
                status           = "new",
                enriched         = False,
                score_fiabilite  = 0.0,
                scraped_at       = datetime.utcnow(),
            )
            db.add(lead)
            new_leads_objs.append(lead)
            inserted += 1

        db.commit()
        # Récupérer les IDs des nouveaux leads après commit
        new_lead_ids = [l.id for l in new_leads_objs]
        logger.info(f"[SCRAPING] {inserted} leads insérés en base (IDs: {new_lead_ids})")

        # 5. Marquer le job comme terminé (update direct par id pour éviter
        #    une instance expirée par les commits précédents)
        db.query(ScrapingJob).filter(ScrapingJob.id == job_id).update({
            "status": "termine",
            "finished_at": datetime.utcnow(),
            "leads_collected": inserted,
            "success_rate": 100.0 if inserted > 0 else 0.0,
        })
        db.commit()
        logger.info(f"[SCRAPING] Job {job_id} terminé — {inserted} leads")

        if inserted > 0:
            try:
                from app.routers.notifications import push_notification
                push_notification("lead", "Nouveaux leads collectés",
                    f"{inserted} nouveaux leads ajoutés par le scraping")
            except Exception as e:
                logger.error(f"[NOTIF] {e}")

        # 6. Pipeline automatique : enrich score retrain si seuil rescore all segment
        if inserted > 0:
            logger.info(f"[SCRAPING] Lancement pipeline sur {inserted} nouveaux leads")
            try:
                from app.pipeline import run_pipeline
                run_pipeline(new_lead_ids=new_lead_ids)
            except Exception as e:
                logger.warning(f"[SCRAPING] Pipeline échoué (non bloquant): {e}")

        return {"job_id": job_id, "inserted": inserted}

    except Exception as e:
        logger.error(f"[SCRAPING] Erreur job {job_id}: {e}")
        try:
            job = db.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
            if job:
                job.status        = "erreur"
                job.error_message = str(e)[:255]
                db.commit()
        except Exception:
            pass
        return {"job_id": job_id, "error": str(e)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.retrain_closing_model")
def retrain_closing_model():
    """Réentraîne le modèle de closing sur les vrais deals clôturés si le seuil est atteint."""
    from app.closing_retrain import retrain_closing_on_real
    return retrain_closing_on_real()


# SÉLECTION AUTOMATIQUE DU GAGNANT A/B APRÈS 24H
@celery_app.task(name="app.tasks.select_ab_winner")
def select_ab_winner():
    """
    Compare les taux d'ouverture des versions A et B sur les emails envoyés
    il y a plus de 24h, puis stocke le gagnant dans Redis.
    Lancée automatiquement toutes les heures par Celery Beat.
    """
    db = SyncSessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(hours=24)

        rows = db.execute(
            text("""
                SELECT
                    ab_version,
                    COUNT(*) FILTER (WHERE email_sent = TRUE)        AS sent,
                    COUNT(*) FILTER (WHERE email_opened = TRUE)       AS opened
                FROM leads
                WHERE ab_version IS NOT NULL
                  AND email_sent = TRUE
                  AND email_sent_at < :cutoff
                GROUP BY ab_version
            """),
            {"cutoff": cutoff},
        ).fetchall()

        if not rows:
            logger.info("[AB] Aucun email envoyé depuis plus de 24h — pas de gagnant encore")
            return {"winner": None, "reason": "no_data"}

        stats = {}
        for row in rows:
            sent   = row.sent   or 0
            opened = row.opened or 0
            stats[row.ab_version] = {
                "sent":      sent,
                "opened":    opened,
                "open_rate": round(opened / sent * 100, 1) if sent > 0 else 0.0,
            }

        # Minimum 10 envois par version pour trancher
        a = stats.get("A", {})
        b = stats.get("B", {})

        if a.get("sent", 0) < 10 or b.get("sent", 0) < 10:
            logger.info(f"[AB] Pas assez de données (A:{a.get('sent',0)} / B:{b.get('sent',0)} envois)")
            result = {
                "winner":    None,
                "reason":    "insufficient_data",
                "min_required": 10,
                "stats":     stats,
                "decided_at": datetime.utcnow().isoformat(),
            }
        else:
            winner = "A" if a["open_rate"] >= b["open_rate"] else "B"
            logger.info(f"[AB] Gagnant : Version {winner} — A={a['open_rate']}% / B={b['open_rate']}%")
            result = {
                "winner":     winner,
                "reason":     "decided",
                "stats":      stats,
                "decided_at": datetime.utcnow().isoformat(),
            }

        # Stocker dans Redis (TTL 48h)
        r_client = redis.Redis(host='localhost', port=6379, db=0)
        r_client.setex("ab_winner_result", 172800, json.dumps(result))

        return result

    except Exception as e:
        logger.error(f"[AB] Erreur select_ab_winner: {e}")
        return {"winner": None, "error": str(e)}
    finally:
        db.close()


# RELANCE EMAIL AUTOMATIQUE J+3 (si pas d'ouverture)
@celery_app.task(name="app.tasks.send_followup_emails")
def send_followup_emails():
    """
    Envoie une relance aux leads dont l'email a été envoyé il y a 3+ jours
    sans ouverture, et dont la relance n'a pas encore été envoyée.
    Lancée automatiquement chaque matin via Celery Beat.
    """
    import os
    from dotenv import load_dotenv
    import requests

    load_dotenv()
    BREVO_API_KEY = os.getenv("BREVO_API_KEY")
    FROM_EMAIL    = os.getenv("FROM_EMAIL", "contact@leadpilot.tn")
    FROM_NAME     = os.getenv("FROM_NAME", "LeadPilot")

    if not BREVO_API_KEY:
        logger.warning("[FOLLOWUP] BREVO_API_KEY manquante — arrêt")
        return {"sent": 0, "reason": "no_brevo_key"}

    db = SyncSessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=3)

        # Leads éligibles : email envoyé, pas ouvert, pas de relance déjà envoyée
        rows = db.execute(text("""
            SELECT id, email, company, first_name, last_name,
                   email_subject_a, email_body_a, ab_version
            FROM leads
            WHERE email_sent = TRUE
              AND email_opened = FALSE
              AND followup_sent = FALSE
              AND email_sent_at < :cutoff
              AND email IS NOT NULL
            ORDER BY lead_score DESC NULLS LAST
            LIMIT 50
        """), {"cutoff": cutoff}).fetchall()

        logger.info(f"[FOLLOWUP] {len(rows)} leads éligibles à la relance")
        sent_count = 0

        for row in rows:
            lead_id  = row.id
            to_email = row.email
            company  = row.company or "votre entreprise"
            fname    = row.first_name or ""
            greeting = f"Bonjour {fname}," if fname else f"Bonjour,"

            # Objet de relance
            orig_subject = row.email_subject_a or "Notre proposition"
            relance_subject = f"Re: {orig_subject}"

            # Corps de relance court
            relance_body = (
                f"{greeting}\n\n"
                f"Je me permets de revenir vers vous concernant mon email de la semaine dernière "
                f"au sujet de {company}.\n\n"
                f"Avez-vous eu l'occasion d'en prendre connaissance ? "
                f"Je serais ravi(e) d'échanger 15 minutes avec vous pour voir comment LeadPilot "
                f"peut vous aider concrètement.\n\n"
                f"Répondez simplement à cet email pour convenir d'un créneau.\n\n"
                f"Cordialement,\n"
                f"L'équipe LeadPilot\n"
                f"contact@leadpilot.tn | www.leadpilot.tn"
            )

            to_name = f"{fname} — {company}".strip(" —") if fname else company

            try:
                resp = requests.post(
                    "https://api.brevo.com/v3/smtp/email",
                    headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
                    json={
                        "sender": {"name": FROM_NAME, "email": FROM_EMAIL},
                        "to": [{"email": to_email, "name": to_name}],
                        "subject": relance_subject,
                        "textContent": relance_body,
                        "htmlContent": f"<p>{relance_body.replace(chr(10), '<br>')}</p>",
                    },
                    timeout=15,
                )
                if resp.status_code in (200, 201):
                    db.execute(text("""
                        UPDATE leads SET followup_sent=TRUE, followup_sent_at=:ts
                        WHERE id=:id
                    """), {"ts": datetime.utcnow(), "id": lead_id})
                    sent_count += 1
                    logger.info(f"[FOLLOWUP] Relance envoyée {to_email}")
                else:
                    logger.warning(f"[FOLLOWUP] Brevo erreur {resp.status_code}: {resp.text[:100]}")
            except Exception as e:
                logger.warning(f"[FOLLOWUP] Erreur envoi {to_email}: {e}")

        db.commit()
        logger.info(f"[FOLLOWUP] Terminé — {sent_count} relances envoyées")
        return {"sent": sent_count, "eligible": len(rows)}

    except Exception as e:
        logger.error(f"[FOLLOWUP] Erreur: {e}")
        db.rollback()
        return {"sent": 0, "error": str(e)}
    finally:
        db.close()