from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db, SyncSessionLocal
from app.models.workflow import Workflow
from app.models.lead import Lead
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger("leadpilot.workflows")
router = APIRouter()

class WorkflowCreate(BaseModel):
    name: str
    trigger: Optional[str] = "manual"
    description: Optional[str] = None
    actions: Optional[str] = "email"

class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    trigger: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None


# Logique réelle d'exécution
def _execute_workflow_real(workflow_id: int):
    """Exécute vraiment le workflow selon son trigger."""
    from app.email_generator import generate_email_openrouter, send_email_brevo

    db = SyncSessionLocal()
    try:
        wf = db.query(Workflow).filter(Workflow.id == workflow_id).first()
        if not wf or wf.status != "active":
            return

        trigger = wf.trigger
        leads = []

        # Sélection des leads selon le trigger
        if trigger == "new_lead":
            # Leads ajoutés récemment (derniers 7 jours) non encore contactés
            from datetime import datetime, timedelta
            cutoff = datetime.utcnow() - timedelta(days=7)
            leads = db.query(Lead).filter(
                Lead.email.isnot(None),
                Lead.email_sent == False,
                Lead.scraped_at >= cutoff,
            ).limit(20).all()

        elif trigger == "score_high":
            # Leads chauds (score >= 70) pas encore contactés
            leads = db.query(Lead).filter(
                Lead.email.isnot(None),
                Lead.lead_score >= 70,
                Lead.email_sent == False,
            ).limit(20).all()

        elif trigger == "no_email":
            # Leads avec email mais jamais contactés
            leads = db.query(Lead).filter(
                Lead.email.isnot(None),
                Lead.email_sent == False,
                Lead.lead_score.isnot(None),
            ).order_by(Lead.lead_score.desc()).limit(20).all()

        elif trigger == "deal_won":
            # Leads chauds ou "Prêts à Acheter"
            leads = db.query(Lead).filter(
                Lead.email.isnot(None),
                Lead.segment.in_(["Chaud", "Prêts à Acheter"]),
                Lead.email_sent == False,
            ).limit(10).all()

        elif trigger == "manual":
            # Tous les leads avec email non encore contactés
            leads = db.query(Lead).filter(
                Lead.email.isnot(None),
                Lead.email_sent == False,
            ).limit(10).all()

        if not leads:
            logger.info(f"[Workflow {wf.name}] Aucun lead éligible pour trigger={trigger}")
            wf.executions = (wf.executions or 0) + 1
            db.commit()
            return

        logger.info(f"[Workflow {wf.name}] {len(leads)} leads trouvés pour trigger={trigger}")

        # Génération + envoi email pour chaque lead
        sent_count = 0
        tone = "professionnel"
        cta = "Planifier un appel de 15 minutes"

        SUBJECT_BY_TRIGGER = {
            "new_lead":   "Bienvenue — découvrez comment LeadPilot peut transformer votre prospection",
            "score_high": "Vous êtes sur notre radar — parlons de votre croissance",
            "no_email":   "Une opportunité que vous ne voudrez pas manquer",
            "deal_won":   "Merci pour votre confiance — prochaines étapes",
            "manual":     "Une proposition personnalisée pour votre entreprise",
        }
        subject = SUBJECT_BY_TRIGGER.get(trigger, "Un message personnalisé de LeadPilot")

        for lead in leads:
            try:
                lead_dict = {
                    "company": lead.company or "",
                    "sector":  lead.sector  or "Services",
                    "region":  lead.region  or "Tunisie",
                    "email":   lead.email,
                    "phone":   lead.phone   or "",
                    "website": lead.website or "",
                    "lead_score": lead.lead_score or 50,
                }
                result = generate_email_openrouter(
                    lead=lead_dict,
                    segment=lead.segment or "Froid",
                    version="A",
                    user_subject=subject,
                    user_cta=cta,
                    user_tone=tone,
                )
                if result and result.get("subject") and result.get("body"):
                    ok = send_email_brevo(
                        to_email=lead.email,
                        to_name=lead.company or lead.email,
                        subject=result["subject"],
                        body=result["body"],
                        lead_id=lead.id,
                        cta_text=cta or "En savoir plus",
                    )
                    if ok:
                        from datetime import datetime
                        lead.email_sent      = True
                        lead.email_sent_at   = datetime.utcnow()
                        lead.email_subject_a = result["subject"]
                        lead.email_body_a    = result["body"]
                        lead.status          = "contacté"
                        sent_count += 1
                        logger.info(f"   Email envoyé à {lead.email}")
                    else:
                        logger.warning(f" Échec envoi à {lead.email}")
            except Exception as e:
                logger.error(f" Erreur lead {lead.id}: {e}")

        # Mise à jour compteurs
        wf.executions  = (wf.executions  or 0) + 1
        wf.emails_sent = (wf.emails_sent or 0) + sent_count
        db.commit()
        logger.info(f"[Workflow {wf.name}] Terminé — {sent_count}/{len(leads)} emails envoyés")

    except Exception as e:
        logger.error(f"[Workflow execute] Erreur: {e}")
        db.rollback()
    finally:
        db.close()


# Trigger automatique post-scraping

def trigger_new_lead_workflows(lead_ids: list):
    """
    Déclenché automatiquement par le pipeline après insertion de nouveaux leads.
    Exécute tous les workflows actifs avec trigger='new_lead' sur ces leads précis.
    """
    if not lead_ids:
        return

    db = SyncSessionLocal()
    try:
        from app.email_generator import generate_email_openrouter, send_email_brevo
        from datetime import datetime

        # Récupérer tous les workflows actifs sur trigger new_lead
        workflows = db.query(Workflow).filter(
            Workflow.trigger == "new_lead",
            Workflow.status == "active",
        ).all()

        if not workflows:
            logger.info("[WorkflowTrigger] Aucun workflow actif sur new_lead")
            return

        # Récupérer les leads éligibles parmi les nouveaux (avec email, pas encore contactés)
        leads = db.query(Lead).filter(
            Lead.id.in_(lead_ids),
            Lead.email.isnot(None),
            Lead.email_sent == False,
        ).all()

        if not leads:
            logger.info(f"[WorkflowTrigger] Aucun lead éligible parmi {len(lead_ids)} nouveaux (pas d'email ou déjà contacté)")
            return

        logger.info(f"[WorkflowTrigger] {len(workflows)} workflow(s) × {len(leads)} leads éligibles")

        for wf in workflows:
            sent_count = 0
            subject = "Bienvenue — découvrez comment LeadPilot peut transformer votre prospection"

            for lead in leads:
                try:
                    lead_dict = {
                        "company":    lead.company    or "",
                        "sector":     lead.sector     or "Services",
                        "region":     lead.region     or "Tunisie",
                        "email":      lead.email,
                        "lead_score": lead.lead_score or 50,
                    }
                    result = generate_email_openrouter(
                        lead=lead_dict,
                        segment=lead.segment or "Froid",
                        version="A",
                        user_subject=subject,
                        user_cta="Planifier un appel de 15 minutes",
                        user_tone="professionnel",
                    )
                    if result and result.get("subject") and result.get("body"):
                        ok = send_email_brevo(
                            to_email=lead.email,
                            to_name=lead.company or lead.email,
                            subject=result["subject"],
                            body=result["body"],
                            lead_id=lead.id,
                            cta_text="Planifier un appel de 15 minutes",
                        )
                        if ok:
                            lead.email_sent      = True
                            lead.email_sent_at   = datetime.utcnow()
                            lead.email_subject_a = result["subject"]
                            lead.email_body_a    = result["body"]
                            lead.status          = "contacté"
                            sent_count += 1
                            logger.info(f"   [Workflow '{wf.name}'] Email envoyé {lead.email}")
                except Exception as e:
                    logger.error(f" Lead {lead.id}: {e}")

            wf.executions  = (wf.executions  or 0) + 1
            wf.emails_sent = (wf.emails_sent or 0) + sent_count
            db.commit()
            logger.info(f"[WorkflowTrigger] '{wf.name}' — {sent_count}/{len(leads)} emails envoyés")

    except Exception as e:
        logger.error(f"[WorkflowTrigger] Erreur: {e}")
        db.rollback()
    finally:
        db.close()


# Endpoints

@router.get("/")
async def list_workflows(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Workflow).order_by(Workflow.created_at.desc()))
    workflows = result.scalars().all()
    return [
        {
            "id": w.id, "name": w.name, "trigger": w.trigger,
            "status": w.status, "description": w.description,
            "actions": w.actions, "executions": w.executions,
            "emails_sent": w.emails_sent,
            "created_at": w.created_at.isoformat() if w.created_at else None,
        }
        for w in workflows
    ]

@router.post("/")
async def create_workflow(data: WorkflowCreate, db: AsyncSession = Depends(get_db)):
    wf = Workflow(
        name=data.name, trigger=data.trigger,
        description=data.description, actions=data.actions,
        status="active", executions=0, emails_sent=0,
    )
    db.add(wf)
    await db.commit()
    await db.refresh(wf)
    return {"id": wf.id, "name": wf.name, "status": wf.status, "trigger": wf.trigger,
            "description": wf.description, "actions": wf.actions,
            "executions": wf.executions, "emails_sent": wf.emails_sent}

@router.patch("/{id}")
async def update_workflow(id: int, data: WorkflowUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Workflow).where(Workflow.id == id))
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(404, "Workflow non trouvé")
    if data.name is not None:        wf.name = data.name
    if data.trigger is not None:     wf.trigger = data.trigger
    if data.status is not None:      wf.status = data.status
    if data.description is not None: wf.description = data.description
    await db.commit()
    return {"id": wf.id, "status": wf.status, "name": wf.name}

@router.post("/{id}/execute")
async def execute_workflow(
    id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Workflow).where(Workflow.id == id))
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(404, "Workflow non trouvé")
    if wf.status != "active":
        raise HTTPException(400, "Workflow en pause — activez-le d'abord")

    # Lance l'exécution réelle en arrière-plan
    background_tasks.add_task(_execute_workflow_real, id)

    return {
        "message": f"Workflow '{wf.name}' lancé — les emails seront envoyés en arrière-plan",
        "trigger": wf.trigger,
        "status": "running"
    }

@router.get("/{id}/sent-emails")
async def get_sent_emails(id: int, db: AsyncSession = Depends(get_db)):
    """Retourne les derniers emails envoyés par ce workflow (leads avec email_sent=True)."""
    from datetime import datetime, timedelta
    result = await db.execute(select(Workflow).where(Workflow.id == id))
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(404, "Workflow non trouvé")

    # Récupère les leads contactés récemment (dernières 24h)
    cutoff = datetime.utcnow() - timedelta(hours=24)
    leads_result = await db.execute(
        select(Lead).where(
            Lead.email_sent == True,
            Lead.email_sent_at >= cutoff,
            Lead.email_subject_a.isnot(None),
        ).order_by(Lead.email_sent_at.desc()).limit(50)
    )
    leads = leads_result.scalars().all()
    return [
        {
            "id": l.id,
            "company":  l.company,
            "email":    l.email,
            "segment":  l.segment,
            "score":    l.lead_score,
            "subject":  l.email_subject_a,
            "body":     l.email_body_a,
            "sent_at":  l.email_sent_at.isoformat() if l.email_sent_at else None,
        }
        for l in leads
    ]

@router.delete("/{id}")
async def delete_workflow(id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Workflow).where(Workflow.id == id))
    wf = result.scalar_one_or_none()
    if wf:
        await db.delete(wf)
        await db.commit()
    return {"message": "Supprimé"}

@router.get("/stats/summary")
async def workflow_stats(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Workflow))
    workflows = result.scalars().all()
    return {
        "total":       len(workflows),
        "active":      sum(1 for w in workflows if w.status == "active"),
        "executions":  sum(w.executions  or 0 for w in workflows),
        "emails_sent": sum(w.emails_sent or 0 for w in workflows),
    }
