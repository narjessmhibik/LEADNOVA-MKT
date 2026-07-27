from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.scraping_job import ScrapingJob
from app.models.lead import Lead
from datetime import datetime
import logging, os, shutil
from pathlib import Path

logger = logging.getLogger("leadpilot.scraping")
router = APIRouter()


@router.get("/stats")
async def get_scraping_stats(db: AsyncSession = Depends(get_db)):
    """KPIs globaux du module scraping"""
    jobs_result = await db.execute(select(ScrapingJob))
    jobs = jobs_result.scalars().all()

    actifs     = sum(1 for j in jobs if j.status == "actif")
    en_attente = sum(1 for j in jobs if j.status == "en_attente")
    termines   = [j for j in jobs if j.status == "termine"]
    taux = round(sum(j.success_rate for j in termines) / len(termines), 1) if termines else 0.0

    # Nombre total de leads en base
    leads_count_result = await db.execute(select(func.count(Lead.id)))
    total_leads = leads_count_result.scalar() or 0

    return {
        "jobs_actifs":      actifs,
        "leads_collectes":  total_leads,
        "en_attente":       en_attente,
        "taux_succes":      taux,
        "total_jobs":       len(jobs),
    }


@router.get("/jobs")
async def get_jobs(db: AsyncSession = Depends(get_db)):
    """Liste tous les jobs de scraping"""
    result = await db.execute(
        select(ScrapingJob).order_by(ScrapingJob.created_at.desc())
    )
    return result.scalars().all()


@router.post("/jobs")
async def create_job(data: dict, db: AsyncSession = Depends(get_db)):
    """Crée un nouveau job de scraping"""
    job = ScrapingJob(
        name      = data.get("name", "Job sans nom"),
        source    = data.get("source", "Google Maps"),
        keywords  = data.get("keywords") or None,
        location  = data.get("location") or None,
        sector    = data.get("sector") or None,
        max_leads = int(data.get("maxLeads", 100)),
        status    = "en_attente",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    logger.info(f"Job créé : {job.name} | source={job.source}")
    return job


@router.post("/jobs/{job_id}/start")
async def start_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """
    Démarre un job de scraping.
    Essaie d'abord via Celery (background). Si Celery indisponible,
    exécute le scraping en direct (mode synchrone) dans un thread séparé.
    """
    result = await db.execute(select(ScrapingJob).where(ScrapingJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job introuvable")
    if job.status == "actif":
        raise HTTPException(status_code=400, detail="Job déjà en cours")

    # Utiliser Celery uniquement si un worker répond, sinon exécution directe
    try:
        from app.celery_app import celery_app
        from app.tasks import run_scraping_job
        replies = celery_app.control.ping(timeout=1.0)
        if replies:
            task = run_scraping_job.delay(job_id)
            logger.info(f"Tâche Celery lancée pour job {job_id} : task_id={task.id}")
            return {"message": "Scraping lancé via Celery", "job_id": job_id, "task_id": task.id, "mode": "celery"}
        logger.warning("Aucun worker Celery actif — mode direct activé")
    except Exception as celery_err:
        logger.warning(f"Celery indisponible ({celery_err}) — mode direct activé")

    # Fallback : exécution directe dans un thread (sans bloquer l'API)
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    def _run_direct():
        from app.tasks import run_scraping_job as _task_fn
        return _task_fn(job_id)

    loop = asyncio.get_event_loop()
    loop.run_in_executor(ThreadPoolExecutor(max_workers=1), _run_direct)
    logger.info(f"Job {job_id} lancé en mode direct (thread)")
    return {"message": "Scraping lancé en mode direct", "job_id": job_id, "task_id": None, "mode": "direct"}


@router.patch("/jobs/{job_id}/status")
async def update_job_status(job_id: int, data: dict, db: AsyncSession = Depends(get_db)):
    """Met à jour manuellement le statut d'un job"""
    result = await db.execute(select(ScrapingJob).where(ScrapingJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job introuvable")

    new_status = data.get("status")
    if new_status:
        job.status = new_status
        if new_status == "actif" and not job.started_at:
            job.started_at = datetime.utcnow()
        if new_status == "termine":
            job.finished_at = datetime.utcnow()
            job.leads_collected = data.get("leads_collected", job.leads_collected)
            job.success_rate    = data.get("success_rate", 100.0)

    await db.commit()
    await db.refresh(job)
    return job


@router.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    """Sauvegarde un fichier CSV dans scraping/data/ pour l'Import CSV."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "Seuls les fichiers .csv sont acceptés")

    data_dir = Path(__file__).parent.parent.parent / "scraping" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    dest = data_dir / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {"message": f"Fichier '{file.filename}' uploadé", "path": str(dest)}


@router.get("/linkedin/status")
async def linkedin_status():
    """Vérifie si la session LinkedIn existe"""
    import os
    exists = os.path.exists("linkedin_session.json")
    return {
        "session_exists": exists,
        "message": "Session LinkedIn active" if exists else "Pas de session — connexion requise"
    }


@router.post("/linkedin/create-session")
async def create_linkedin_session(data: dict):
    """
    Crée une session LinkedIn via Playwright.
    Body: { email: str, password: str }
    Lance un navigateur visible pour se connecter.
    """
    import asyncio

    async def _create():
        from app.linkedin_scraper.core.browser import BrowserManager
        email    = data.get("email", "")
        password = data.get("password", "")
        if not email or not password:
            raise ValueError("Email et mot de passe requis")

        async with BrowserManager(headless=False) as browser:
            page = browser.page
            await page.goto("https://www.linkedin.com/login")
            await page.fill("#username", email)
            await page.fill("#password", password)
            await page.click("button[type='submit']")
            await page.wait_for_timeout(5000)
            # Sauvegarder la session
            await browser.save_session("linkedin_session.json")

    try:
        await asyncio.get_event_loop().run_in_executor(None, lambda: asyncio.run(_create()))
        return {"message": "Session LinkedIn créée avec succès", "session_file": "linkedin_session.json"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur connexion LinkedIn: {str(e)}")


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Annule un job de scraping en cours"""
    result = await db.execute(select(ScrapingJob).where(ScrapingJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job introuvable")
    if job.status in ("termine", "annule", "erreur"):
        return job
    job.status      = "annule"
    job.finished_at = datetime.utcnow()
    await db.commit()
    await db.refresh(job)
    return job


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Supprime un job"""
    result = await db.execute(select(ScrapingJob).where(ScrapingJob.id == job_id))
    job = result.scalar_one_or_none()
    if job:
        await db.delete(job)
        await db.commit()
    return {"message": "Job supprimé"}


@router.get("/recent-leads")
async def get_recent_leads(db: AsyncSession = Depends(get_db), limit: int = 10):
    """Derniers leads collectés"""
    result = await db.execute(
        select(Lead)
        .order_by(Lead.created_at.desc())
        .limit(limit)
    )
    leads = result.scalars().all()
    return [
        {
            "id":      l.id,
            "company": l.company,
            "sector":  l.sector,
            "region":  l.region,
            "email":   l.email,
            "phone":   l.phone,
            "score":   l.lead_score,
            "segment": l.segment,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in leads
    ]
