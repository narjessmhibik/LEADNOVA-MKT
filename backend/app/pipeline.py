import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("leadpilot.pipeline")

RETRAIN_THRESHOLD = 200  # réentraîner quand >= 200 nouveaux leads scorés depuis le dernier entraînement


def _count_leads_since(engine, trained_at: datetime) -> int:
    """Nombre de leads scorés après la date du dernier entraînement."""
    from sqlalchemy import text
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT COUNT(*) FROM leads WHERE lead_score IS NOT NULL AND scored_at > :ts"
        ), {"ts": trained_at})
        return result.scalar() or 0


def run_pipeline(new_lead_ids: list = None):
    """
    Pipeline complet déclenché après chaque scraping.
    1. Enrichissement des nouveaux leads
    2. Scoring XGBoost (nouveaux uniquement)
    3. Réentraînement si >= RETRAIN_THRESHOLD nouveaux leads depuis le dernier train
    4. Si retrain : rescore TOUS les leads avec le nouveau modèle
    5. Segmentation K-Means globale
    """
    logger.info("\n Pipeline automatique démarré")
    if new_lead_ids:
        logger.info(f"   {len(new_lead_ids)} nouveaux leads à traiter")

    # 1. Enrichissement
    if new_lead_ids:
        try:
            from app.enrichment import enrich_leads
            logger.info(" Enrichissement...")
            enrich_leads(batch_size=len(new_lead_ids), only_incomplete=False, lead_ids=new_lead_ids)
            logger.info("   Enrichissement terminé")
        except Exception as e:
            logger.warning(f" Enrichissement échoué (non bloquant): {e}")

    # 2. Scoring XGBoost — nouveaux leads uniquement
    try:
        from app.scoring import score_leads
        logger.info(" Scoring nouveaux leads...")
        score_leads(rescore_all=False)
        logger.info("   Scoring terminé")
    except Exception as e:
        logger.warning(f" Scoring échoué (non bloquant): {e}")
        # Si le scoring échoue on continue quand même vers la segmentation

    # 3. Workflows automation — déclenchement auto sur les nouveaux leads
    try:
        from app.routers.workflows import trigger_new_lead_workflows
        logger.info("   Workflows automation...")
        trigger_new_lead_workflows(new_lead_ids)
        logger.info("   Workflows terminés")
    except Exception as e:
        logger.warning(f"   Workflows échoués (non bloquant): {e}")

    # 5. Vérifier si on doit réentraîner
    retrained = False
    try:
        import joblib
        from sqlalchemy import create_engine
        import os
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

        model_path = Path(__file__).parent / "models" / "xgboost_model.pkl"
        if model_path.exists():
            data = joblib.load(model_path)
            trained_at_str = data.get("trained_at")
            if trained_at_str:
                trained_at = datetime.fromisoformat(trained_at_str)
                db_url = os.getenv("DATABASE_URL")
                engine = create_engine(db_url)
                new_since_train = _count_leads_since(engine, trained_at)
                logger.info(f" {new_since_train} leads scorés depuis le dernier entraînement ({trained_at.strftime('%d/%m %H:%M')})")

                if new_since_train >= RETRAIN_THRESHOLD:
                    logger.info(f" Seuil atteint ({new_since_train} >= {RETRAIN_THRESHOLD}) — réentraînement XGBoost...")
                    retrained = _retrain()
                else:
                    logger.info(f"   ⏳ Pas encore assez de données ({new_since_train}/{RETRAIN_THRESHOLD}) — pas de réentraînement")
        else:
            logger.info(" Aucun modèle existant — entraînement initial...")
            retrained = _retrain()
    except Exception as e:
        logger.warning(f" Vérification retrain échouée: {e}")

    # 6. Si retrain : rescore TOUS les leads
    if retrained:
        try:
            from app.scoring import score_leads
            logger.info(" Rescoring global avec le nouveau modèle...")
            score_leads(rescore_all=True)
            logger.info("   Rescoring global terminé")
        except Exception as e:
            logger.warning(f" Rescoring global échoué: {e}")

    # 7. Segmentation K-Means globale
    try:
        from app.kmeans import run_kmeans
        logger.info(" Segmentation K-Means...")
        run_kmeans()
        logger.info("   Segmentation terminée")
    except Exception as e:
        logger.warning(f" Segmentation échouée: {e}")

    logger.info("Pipeline terminé\n")


def _retrain() -> bool:
    """Réentraîne XGBoost. Retourne True si succès."""
    try:
        from app.train_model import train
        train()
        logger.info("   Réentraînement XGBoost terminé")
        return True
    except Exception as e:
        logger.error(f" Réentraînement échoué: {e}")
        return False
