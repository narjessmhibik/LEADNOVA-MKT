from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, text
from app.database import get_db
import redis as redis_lib
import json
import os
import joblib
import pandas as pd
import numpy as np
from app.models.campaign import Campaign
from app.models.lead import Lead
from typing import Optional
from datetime import datetime
import logging

logger = logging.getLogger("leadpilot.campaigns")

# Chargement modèle ML Timing
_MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models")

def _load_timing_model():
    try:
        model      = joblib.load(os.path.join(_MODELS_DIR, "timing_model.pkl"))
        le_segment = joblib.load(os.path.join(_MODELS_DIR, "timing_le_segment.pkl"))
        le_secteur = joblib.load(os.path.join(_MODELS_DIR, "timing_le_secteur.pkl"))
        return model, le_segment, le_secteur
    except Exception:
        return None, None, None

router = APIRouter()

SECTEURS_DISPONIBLES = [
    "Informatique & Tech", "Services aux entreprises",
    "Marketing & Communication", "Santé", "Education & Formation",
    "Industrie & Production", "Construction & BTP", "Immobilier",
]
JOURS_LABEL = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


@router.get("/ml-timing")
async def get_ml_timing(
    segment: str = Query(..., description="Segment cible"),
    secteur: str = Query("Informatique & Tech", description="Secteur d'activité"),
    db: AsyncSession = Depends(get_db),
):
    """
    Recommandation ML du meilleur horaire d'envoi email.
    Utilise Random Forest entraîné sur données synthétiques B2B.
    Bascule automatiquement sur données réelles dès 200 ouvertures.
    """
    model, le_segment, le_secteur = _load_timing_model()
    if model is None:
        raise HTTPException(status_code=500, detail="Modèle ML timing non disponible")

    # Vérifier si le segment existe dans l'encodeur
    if segment not in le_segment.classes_:
        raise HTTPException(status_code=400, detail=f"Segment inconnu : {segment}")

    # Secteur par défaut si inconnu
    if secteur not in le_secteur.classes_:
        secteur = "Informatique & Tech"

    seg_enc = int(le_segment.transform([segment])[0])
    sec_enc = int(le_secteur.transform([secteur])[0])

    # Vérifier combien d'ouvertures réelles on a
    opens_result = await db.execute(
        select(func.count(Lead.id)).where(
            Lead.email_opened == True,
            Lead.email_opened_at != None,
            Lead.segment == segment,
        )
    )
    real_opens = opens_result.scalar() or 0
    source = "real" if real_opens >= 200 else "synthetic"

    # Scanner tous les créneaux semaine (heure 6-21, jour 0-6)
    grid = pd.DataFrame(
        [(h, d, seg_enc, sec_enc) for h in range(6, 22) for d in range(0, 7)],
        columns=["heure", "jour", "segment_enc", "secteur_enc"],
    )
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        scores = model.predict(grid)
    grid["score"] = scores

    # Top 3 créneaux
    top3 = grid.nlargest(3, "score")
    top3_list = [
        {
            "jour": JOURS_LABEL[int(r["jour"])],
            "heure": f"{int(r['heure']):02d}:00",
            "score": round(float(r["score"]) * 100, 1),
        }
        for _, r in top3.iterrows()
    ]

    best = top3_list[0]

    return {
        "segment":        segment,
        "secteur":        secteur,
        "meilleur_jour":  best["jour"],
        "meilleure_heure": best["heure"],
        "score":          best["score"],
        "top_3":          top3_list,
        "source":         source,
        "real_opens":     real_opens,
        "message": (
            f"Basé sur {real_opens} ouvertures réelles"
            if source == "real"
            else f"Basé sur benchmarks B2B ({real_opens} ouvertures réelles — seuil: 200)"
        ),
    }


@router.get("/history")
async def get_campaign_history(db: AsyncSession = Depends(get_db)):
    """Historique des campagnes triées par date"""
    result = await db.execute(
        select(Campaign).order_by(Campaign.created_at.desc()).limit(20)
    )
    campaigns = result.scalars().all()
    return campaigns


@router.get("/")
async def get_campaigns(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campaign))
    return result.scalars().all()


@router.post("/")
async def create_campaign(data: dict, db: AsyncSession = Depends(get_db)):
    campaign = Campaign(**data)
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return campaign


@router.get("/stats/email")
async def get_email_stats(db: AsyncSession = Depends(get_db)):
    """Statistiques des emails générés / envoyés"""
    result = await db.execute(
        select(
            func.count(Lead.id).label("total_with_email"),
            func.count(Lead.email_subject_a).label("generated"),
            func.count(Lead.email_sent_at).label("sent"),
            func.count(case((Lead.email_opened == True, 1))).label("opened"),
            func.count(case((Lead.email_clicked == True, 1))).label("clicked"),
        ).where(Lead.email != None)
    )
    row = result.one()
    _sent = row.sent or 0

    # Par segment
    seg_result = await db.execute(
        select(Lead.segment, func.count(Lead.id).label("count"))
        .where(Lead.email != None)
        .where(Lead.email_subject_a != None)
        .group_by(Lead.segment)
    )
    by_segment = [{"segment": r.segment, "count": r.count} for r in seg_result]

    return {
        "total_with_email": row.total_with_email,
        "generated": row.generated,
        "sent": row.sent,
        "opened": row.opened,
        "clicked": row.clicked,
        "open_rate":  round((row.opened  / _sent) * 100, 1) if _sent else 0,
        "click_rate": round((row.clicked / _sent) * 100, 1) if _sent else 0,
        "pending": row.total_with_email - row.generated,
        "by_segment": by_segment,
    }


@router.get("/stats/engagement")
async def get_engagement_stats(db: AsyncSession = Depends(get_db)):
    """Dashboard KPIs engagement : ouvertures, clics, taux par segment"""
    result = await db.execute(
        select(
            func.count(case((Lead.email_sent == True, 1))).label("sent"),
            func.count(case((Lead.email_opened == True, 1))).label("opened"),
            func.count(case((Lead.email_clicked == True, 1))).label("clicked"),
        )
    )
    row = result.one()

    sent    = row.sent    or 1
    opened  = row.opened  or 0
    clicked = row.clicked or 0

    # Stats par segment
    seg_result = await db.execute(
        select(
            Lead.segment,
            func.count(case((Lead.email_sent == True, 1))).label("sent"),
            func.count(case((Lead.email_opened == True, 1))).label("opened"),
            func.count(case((Lead.email_clicked == True, 1))).label("clicked"),
        )
        .where(Lead.email_sent == True)
        .group_by(Lead.segment)
        .order_by(func.count(case((Lead.email_opened == True, 1))).desc())
    )
    by_segment = [
        {
            "segment": r.segment or "Non segmenté",
            "sent":    r.sent,
            "opened":  r.opened,
            "clicked": r.clicked,
            "open_rate":  round((r.opened  / (r.sent or 1)) * 100, 1),
            "click_rate": round((r.clicked / (r.sent or 1)) * 100, 1),
        }
        for r in seg_result
    ]

    return {
        "sent":       row.sent,
        "opened":     opened,
        "clicked":    clicked,
        "open_rate":  round((opened  / sent) * 100, 1),
        "click_rate": round((clicked / sent) * 100, 1),
        "by_segment": by_segment,
    }


@router.get("/ab-stats")
async def get_ab_stats(db: AsyncSession = Depends(get_db)):
    """Statistiques A/B testing"""
    result = await db.execute(
        select(
            Lead.ab_version,
            func.count(Lead.id).label("total"),
            func.sum(case((Lead.email_sent == True, 1), else_=0)).label("sent"),
            func.sum(case((Lead.email_opened == True, 1), else_=0)).label("opened"),
        )
        .where(Lead.ab_version != None)
        .group_by(Lead.ab_version)
    )
    rows = result.all()
    stats = {}
    for r in rows:
        sent  = r.sent or 0
        opened = r.opened or 0
        stats[r.ab_version] = {
            "total":      r.total,
            "sent":       sent,
            "opened":     opened,
            "open_rate":  round((opened / sent * 100), 1) if sent > 0 else 0,
        }
    return stats


@router.get("/ab-winner")
async def get_ab_winner():
    """Retourne le gagnant A/B sélectionné automatiquement après 24h (stocké dans Redis)"""
    try:
        r = redis_lib.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        raw = r.get("ab_winner_result")
        if not raw:
            return {"winner": None, "message": "Aucun résultat encore — la tâche tourne toutes les heures"}
        return json.loads(raw)
    except Exception as e:
        return {"winner": None, "message": f"Redis indisponible: {e}"}


@router.post("/ab-winner/compute")
async def trigger_ab_winner():
    """Déclenche manuellement la sélection du gagnant A/B via Celery"""
    from app.tasks import select_ab_winner
    task = select_ab_winner.delay()
    return {"message": "Tâche lancée", "task_id": task.id}


@router.get("/preview-emails")
async def preview_generated_emails(
    db: AsyncSession = Depends(get_db),
    segment: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
):
    """Retourne les emails générés avec pagination et recherche"""
    base = select(Lead).where(Lead.email_subject_a != None)

    if segment:
        base = base.where(Lead.segment == segment)
    if search:
        like = f"%{search}%"
        base = base.where(
            Lead.company.ilike(like) | Lead.email.ilike(like)
        )

    # Total
    count_q = select(func.count()).select_from(base.subquery())
    total_result = await db.execute(count_q)
    total = total_result.scalar()

    # Items
    query = base.order_by(Lead.lead_score.desc().nullslast()).offset(offset).limit(limit)
    result = await db.execute(query)
    rows = result.scalars().all()

    items = [
        {
            "id": r.id,
            "company": r.company,
            "email": r.email,
            "sector": r.sector,
            "region": r.region,
            "segment": r.segment,
            "company_type": r.company_type,
            "ab_version": r.ab_version,
            "email_sent": r.email_sent,
            "subject_a": r.email_subject_a,
            "body_a": r.email_body_a,
            "subject_b": r.email_subject_b,
            "body_b": r.email_body_b,
        }
        for r in rows
    ]
    return {"total": total, "items": items}


@router.post("/send-manual")
async def send_manual_email(data: dict, db: AsyncSession = Depends(get_db)):
    """Envoie un email généré par IA à une adresse manuelle + crée le lead s'il n'existe pas"""
    from app.email_generator import generate_email_openrouter, send_email_brevo
    from datetime import datetime

    to_email = data.get("to_email")
    to_name  = data.get("to_name") or to_email
    if not to_email:
        raise HTTPException(status_code=400, detail="Adresse email requise")

    # Chercher ou créer le lead
    result = await db.execute(select(Lead).where(Lead.email == to_email))
    lead_db = result.scalar_one_or_none()
    lead_created = False

    if not lead_db:
        lead_db = Lead(
            company    = to_name,
            email      = to_email,
            source     = "manual",
            status     = "nouveau",
            region     = data.get("region") or "Tunisie",
            sector     = data.get("sector") or None,
            company_type = data.get("company_type") or None,
            created_at = datetime.utcnow(),
        )
        db.add(lead_db)
        await db.flush()  # obtenir l'id avant commit
        lead_created = True

    # Lead dict pour la génération email
    fake_lead = {
        "company":      to_name,
        "sector":       data.get("sector") or lead_db.sector or "Services aux entreprises",
        "region":       data.get("region") or lead_db.region or "Tunisie",
        "company_type": data.get("company_type") or lead_db.company_type or "PME",
        "first_name":   to_name.split()[0] if to_name else "",
    }

    email = generate_email_openrouter(
        lead=fake_lead,
        segment="Chaud",
        version="A",
        user_subject=data.get("subject") or None,
        user_cta=data.get("cta")         or None,
        user_tone=data.get("tone")       or None,
    )

    if not email:
        raise HTTPException(status_code=500, detail="Erreur génération email")

    sent = send_email_brevo(
        to_email=to_email,
        to_name=to_name,
        subject=email["subject"],
        body=email["body"],
        lead_id=lead_db.id,
        cta_text=data.get("cta") or "En savoir plus",
        cta_link=data.get("cta_link") or data.get("ctaLink") or None,
    )

    if not sent:
        raise HTTPException(status_code=500, detail="Erreur envoi Brevo")

    # Mettre à jour le lead avec l'email envoyé
    lead_db.email_sent    = True
    lead_db.email_sent_at = datetime.utcnow()
    lead_db.ab_version    = "A"
    lead_db.email_subject_a = email["subject"]
    lead_db.email_body_a    = email["body"]
    await db.commit()

    return {
        "message":      f"Email envoyé à {to_email}",
        "lead_id":      lead_db.id,
        "lead_created": lead_created,
        "subject": email["subject"],
        "body":    email["body"],
        "preview": email["body"][:200],
    }


@router.post("/webhook/brevo")
async def brevo_webhook(data: dict, db: AsyncSession = Depends(get_db)):
    """
    Webhook Brevo — reçoit les événements d'ouverture d'emails
    Configurer dans Brevo : Transactional > Settings > Webhooks
    Events : opened, clicked
    """
    event     = data.get("event")
    to_email  = data.get("email")
    timestamp = data.get("ts_epoch") or data.get("date")

    logger.info(f"Brevo webhook: event={event} email={to_email}")

    OPEN_EVENTS  = ("opened", "uniqueProxyOpen", "open", "unique_opened")
    CLICK_EVENTS = ("click", "clicked")

    if event in (*OPEN_EVENTS, *CLICK_EVENTS) and to_email:
        result = await db.execute(
            select(Lead).where(Lead.email == to_email).where(Lead.email_sent == True)
        )
        lead = result.scalar_one_or_none()

        if lead:
            if event in OPEN_EVENTS:
                lead.email_opened = True
                lead.email_opened_at = datetime.utcnow()
                lead.status = "qualifié"
            elif event in CLICK_EVENTS:
                lead.email_clicked = True
                lead.email_clicked_at = datetime.utcnow()
                if not lead.email_opened:
                    lead.email_opened = True
                    lead.email_opened_at = datetime.utcnow()
                lead.status = "qualifié"
            await db.commit()
            logger.info(f"Event '{event}' par {to_email} (lead_id={lead.id})")
            return {"status": "ok", "lead_id": lead.id, "event": event}

    return {"status": "ignored", "event": event}




_PIXEL = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
    b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)

@router.get("/track/open")
async def track_email_open(lead_id: int = Query(...), db: AsyncSession = Depends(get_db)):
    """Pixel de tracking 1x1 — marque l'email comme ouvert"""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if lead and not lead.email_opened:
        lead.email_opened = True
        lead.email_opened_at = datetime.utcnow()
        if lead.status in (None, "new", "nouveau", "contacté"):
            lead.status = "qualifié"
        await db.commit()
    return Response(content=_PIXEL, media_type="image/png", headers={"Cache-Control": "no-cache, no-store"})


@router.get("/track/click")
async def track_email_click(
    lead_id: int = Query(...),
    url: str = Query("https://leadpilot.io"),
    db: AsyncSession = Depends(get_db),
):
    """Lien de tracking de clic — enregistre le clic puis redirige vers l'URL de destination"""
    from fastapi.responses import RedirectResponse
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if lead:
        lead.email_clicked = True
        lead.email_clicked_at = datetime.utcnow()
        # un clic implique une ouverture
        if not lead.email_opened:
            lead.email_opened = True
            lead.email_opened_at = datetime.utcnow()
        if lead.status in (None, "new", "nouveau", "contacté"):
            lead.status = "qualifié"
        await db.commit()
    return RedirectResponse(url=url, status_code=302)


@router.delete("/reset-emails")
async def reset_generated_emails(db: AsyncSession = Depends(get_db)):
    """Efface tous les emails générés sur les leads (subjects, bodies, ab_version, sent flags)"""
    from sqlalchemy import update
    from app.models.lead import Lead as LeadModel
    await db.execute(
        update(LeadModel).values(
            email_subject_a=None,
            email_body_a=None,
            email_subject_b=None,
            email_body_b=None,
            ab_version=None,
            email_sent=False,
            email_sent_at=None,
            email_opened=False,
            email_opened_at=None,
        )
    )
    await db.commit()
    return {"message": "Emails générés supprimés"}


@router.get("/{id}")
async def get_campaign(id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campaign).where(Campaign.id == id))
    return result.scalar_one_or_none()


@router.delete("/{id}")
async def delete_campaign(id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campaign).where(Campaign.id == id))
    campaign = result.scalar_one_or_none()
    if campaign:
        await db.delete(campaign)
        await db.commit()
    return {"message": "Campagne supprimée"}


def _run_email_generator(segment: Optional[str], limit: int, dry_run: bool,
                          user_subject: str = None, user_cta: str = None, user_tone: str = None,
                          sector: str = None, region: str = None, lead_ids: list = None,
                          regenerate: bool = False, user_cta_link: str = None):
    """Tâche de fond pour générer les emails"""
    try:
        from app.email_generator import generate_emails
        generate_emails(segment=segment, limit=limit, dry_run=dry_run,
                        user_subject=user_subject, user_cta=user_cta, user_tone=user_tone,
                        sector=sector, region=region, lead_ids=lead_ids, regenerate=regenerate,
                        user_cta_link=user_cta_link)
    except Exception as e:
        logger.error(f"Email generator error: {e}")


@router.post("/generate-emails")
async def trigger_email_generation(
    data: dict,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Lance la génération d'emails en arrière-plan.
    Body: { segment?: string, limit?: int, dry_run?: bool }
    """
    segment      = data.get("segment")       or None
    limit        = min(int(data.get("limit", 50)), 300)
    dry_run      = bool(data.get("dry_run", True))
    user_subject = data.get("subject")        or None
    user_cta     = data.get("cta")            or None
    user_tone    = data.get("tone")           or None
    sector       = data.get("sector")         or None
    region       = data.get("region")         or None
    lead_ids     = data.get("lead_ids")       or None
    regenerate   = bool(data.get("regenerate", False))
    user_cta_link = data.get("cta_link") or data.get("ctaLink") or None
    campaign_name = data.get("campaign_name") or f"Campagne {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}"

    # Sauvegarder dans l'historique
    campaign = Campaign(
        name=campaign_name,
        campaign_name=campaign_name,
        subject=user_subject,
        status="sending" if not dry_run else "draft",
        campaign_status="sending" if not dry_run else "draft",
        channel="email",
        leads_targeted=limit,
        segment_filter=segment,
        sector_filter=sector,
        region_filter=region,
        tone=user_tone,
        cta=user_cta,
    )
    db.add(campaign)
    await db.commit()

    background_tasks.add_task(_run_email_generator, segment, limit, dry_run,
                               user_subject, user_cta, user_tone, sector, region, lead_ids, regenerate,
                               user_cta_link)

    return {
        "message": "Génération lancée en arrière-plan",
        "campaign_id": campaign.id,
        "campaign_name": campaign_name,
        "segment": segment or "tous",
        "limit": limit,
        "dry_run": dry_run,
        "subject": user_subject,
        "cta": user_cta,
        "tone": user_tone,
    }
