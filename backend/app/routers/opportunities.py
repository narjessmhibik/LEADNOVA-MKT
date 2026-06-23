from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.opportunity import Opportunity
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter()


@router.get("/closing-model")
async def closing_model_status(db: AsyncSession = Depends(get_db)):
    """Infos sur le modèle de closing : source (synthétique/réel) + données disponibles."""
    from app.closing import model_info
    from app.closing_retrain import THRESHOLD
    from sqlalchemy import func, case
    info = model_info()
    row = (await db.execute(select(
        func.count(case((Opportunity.stage.in_(["Gagné", "Perdu"]), 1))).label("closed"),
        func.count(case((Opportunity.stage == "Gagné", 1))).label("won"),
        func.count(case((Opportunity.stage == "Perdu", 1))).label("lost"),
    ))).one()
    return {
        "source": info["source"],
        "trained_at": info["trained_at"],
        "closed_deals": row.closed,
        "won": row.won,
        "lost": row.lost,
        "threshold": THRESHOLD,
    }


@router.post("/closing-model/retrain")
async def closing_model_retrain():
    """Déclenche le réentraînement du modèle de closing sur les vrais deals clôturés."""
    from app.closing_retrain import retrain_closing_on_real
    return retrain_closing_on_real()

class OpportunityCreate(BaseModel):
    title: str
    company: Optional[str] = None
    lead_id: Optional[int] = None
    value: Optional[float] = 0.0
    stage: Optional[str] = "Prospection"
    probability: Optional[float] = 30.0
    risk: Optional[bool] = False
    notes: Optional[str] = None

class OpportunityUpdate(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    value: Optional[float] = None
    stage: Optional[str] = None
    probability: Optional[float] = None
    risk: Optional[bool] = None
    notes: Optional[str] = None

@router.get("/")
async def list_opportunities(db: AsyncSession = Depends(get_db)):
    from app.models.lead import Lead
    from app.closing import predict_closing

    result = await db.execute(select(Opportunity).order_by(Opportunity.created_at.desc()))
    opps = result.scalars().all()

    # Récupérer les scores des leads liés en une seule requête
    lead_ids = [o.lead_id for o in opps if o.lead_id]
    scores = {}
    if lead_ids:
        rows = await db.execute(select(Lead.id, Lead.lead_score).where(Lead.id.in_(lead_ids)))
        scores = {r.id: r.lead_score for r in rows}

    out = []
    for o in opps:
        ml_prob = predict_closing(
            stage=o.stage, value=o.value,
            lead_score=scores.get(o.lead_id, 50),
            created_at=o.created_at, risk=o.risk,
        )
        out.append({
            "id": o.id, "title": o.title, "company": o.company,
            "lead_id": o.lead_id, "value": o.value, "stage": o.stage,
            "probability": o.probability, "ml_probability": ml_prob,
            "risk": o.risk, "notes": o.notes,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        })
    return out

@router.post("/convert/{lead_id}")
async def convert_lead_to_opportunity(lead_id: int, db: AsyncSession = Depends(get_db)):
    """Passation Marketing -> Sales : transforme un lead en opportunité dans le pipeline."""
    from app.models.lead import Lead

    lead_res = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = lead_res.scalar_one_or_none()
    if not lead:
        raise HTTPException(404, "Lead introuvable")

    existing = await db.execute(select(Opportunity).where(Opportunity.lead_id == lead_id))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Ce lead a déjà une opportunité")

    # Valeur estimée à partir du score du lead (heuristique simple, éditable ensuite)
    score = lead.lead_score or 30
    est_value = round(5000 + score * 600)

    opp = Opportunity(
        title=f"Projet {lead.company or 'sans nom'}",
        company=lead.company,
        lead_id=lead.id,
        value=est_value,
        stage="Prospection",
        probability=20.0,
        risk=False,
    )
    db.add(opp)
    lead.status = "qualifié"
    await db.commit()
    await db.refresh(opp)

    from app.routers.notifications import push_notification_async
    await push_notification_async(db, "info", "Nouvelle opportunité",
        f'{lead.company or "Lead"} converti en opportunité ({est_value} TND)')

    return {"id": opp.id, "title": opp.title, "company": opp.company,
            "value": opp.value, "stage": opp.stage, "lead_id": opp.lead_id}


@router.post("/")
async def create_opportunity(data: OpportunityCreate, db: AsyncSession = Depends(get_db)):
    opp = Opportunity(
        title=data.title, company=data.company, lead_id=data.lead_id,
        value=data.value, stage=data.stage, probability=data.probability,
        risk=data.risk, notes=data.notes,
    )
    db.add(opp)
    await db.commit()
    await db.refresh(opp)
    if opp.risk:
        from app.routers.notifications import push_notification_async
        await push_notification_async(db, "risk", "Deal à risque",
            f'"{opp.title}" ({opp.company or "—"}) est marqué à risque')
    return {"id": opp.id, "title": opp.title, "company": opp.company,
            "value": opp.value, "stage": opp.stage, "probability": opp.probability,
            "risk": opp.risk, "notes": opp.notes}

@router.patch("/{id}")
async def update_opportunity(id: int, data: OpportunityUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Opportunity).where(Opportunity.id == id))
    opp = result.scalar_one_or_none()
    if not opp:
        raise HTTPException(404, "Deal non trouvé")
    if data.title is not None:       opp.title = data.title
    if data.company is not None:     opp.company = data.company
    if data.value is not None:       opp.value = data.value
    if data.stage is not None:
        opp.stage = data.stage
        # Mettre à jour le statut du lead associé selon le stage
        if data.stage == "Gagné" and opp.lead_id:
            from app.models.lead import Lead
            lead_res = await db.execute(select(Lead).where(Lead.id == opp.lead_id))
            lead = lead_res.scalar_one_or_none()
            if lead:
                lead.status = "converti"
        elif data.stage == "Perdu" and opp.lead_id:
            from app.models.lead import Lead
            lead_res = await db.execute(select(Lead).where(Lead.id == opp.lead_id))
            lead = lead_res.scalar_one_or_none()
            if lead:
                lead.status = "perdu"
    if data.probability is not None: opp.probability = data.probability
    became_risky = data.risk is True and not opp.risk
    if data.risk is not None:        opp.risk = data.risk
    if data.notes is not None:       opp.notes = data.notes
    await db.commit()
    if became_risky:
        from app.routers.notifications import push_notification_async
        await push_notification_async(db, "risk", "Deal à risque",
            f'"{opp.title}" ({opp.company or "—"}) est marqué à risque')

    # Recalculer la probabilité de closing (l'étape vient peut-être de changer)
    from app.models.lead import Lead
    from app.closing import predict_closing
    lead_score = 50
    if opp.lead_id:
        lr = await db.execute(select(Lead.lead_score).where(Lead.id == opp.lead_id))
        lead_score = lr.scalar() or 50
    ml_prob = predict_closing(stage=opp.stage, value=opp.value, lead_score=lead_score,
                              created_at=opp.created_at, risk=opp.risk)

    return {"id": opp.id, "stage": opp.stage, "title": opp.title, "ml_probability": ml_prob}

@router.delete("/{id}")
async def delete_opportunity(id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Opportunity).where(Opportunity.id == id))
    opp = result.scalar_one_or_none()
    if opp:
        await db.delete(opp)
        await db.commit()
    return {"message": "Deal supprimé"}

@router.get("/stats/summary")
async def opportunity_stats(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Opportunity))
    opps = result.scalars().all()
    pipeline = sum(o.value or 0 for o in opps)
    forecast = sum((o.value or 0) * (o.probability or 0) / 100 for o in opps)
    return {
        "total": len(opps),
        "pipeline": round(pipeline, 2),
        "forecast": round(forecast, 2),
        "at_risk": sum(1 for o in opps if o.risk),
        "by_stage": {
            stage: sum(1 for o in opps if o.stage == stage)
            for stage in ["Prospection", "Qualification", "Proposition", "Négociation", "Gagné", "Perdu"]
        }
    }
