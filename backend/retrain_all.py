import sys
import os
import logging

sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("retrain_all.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger("retrain_all")


def main():
    logger.info("=" * 60)
    logger.info("LEADPILOT — RÉENTRAÎNEMENT COMPLET")
    logger.info("=" * 60)

    # 1. XGBoost 
    logger.info("\n[1/4] Réentraînement XGBoost...")
    try:
        from app.train_model import train
        train()
        logger.info(" XGBoost réentraîné")
    except Exception as e:
        logger.error(f" XGBoost erreur: {e}")
        sys.exit(1)

    # 2. Re-score tous les leads 
    logger.info("\n[2/4] Re-scoring de tous les leads enrichis...")
    try:
        from app.scoring import score_leads
        score_leads(rescore_all=True)
        logger.info(" Scoring terminé")
    except Exception as e:
        logger.error(f" Scoring erreur: {e}")
        sys.exit(1)

    # 3. K-Means 
    logger.info("\n[3/4] Réentraînement K-Means...")
    try:
        from app.kmeans import run_kmeans
        run_kmeans()
        logger.info(" K-Means réentraîné")
    except Exception as e:
        logger.error(f" K-Means erreur: {e}")
        sys.exit(1)

    # 4. Timing model — données réelles si seuil atteint
    logger.info("\n[4/4] Vérification timing model...")
    try:
        from pathlib import Path
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=Path(__file__).parent / ".env")
        db_url = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql+psycopg2://").replace("postgresql://", "postgresql+psycopg2://")
        from sqlalchemy import create_engine, text as sql_text
        engine = create_engine(db_url)
        with engine.connect() as conn:
            n_opens = conn.execute(sql_text(
                "SELECT COUNT(*) FROM leads WHERE email_opened = TRUE AND email_opened_at IS NOT NULL AND segment IS NOT NULL AND sector IS NOT NULL"
            )).scalar() or 0

        if n_opens >= 200:
            logger.info(f"   {n_opens} ouvertures réelles — réentraînement timing sur données réelles...")
            from scripts.train_timing_model_real import main as train_timing_real
            train_timing_real()
            logger.info(" Timing model réentraîné sur données réelles")
        else:
            logger.info(f"   {n_opens}/200 ouvertures réelles — modèle synthétique conservé")
    except Exception as e:
        logger.warning(f" Timing model erreur (non bloquant): {e}")

    logger.info("\n" + "=" * 60)
    logger.info(" RÉENTRAÎNEMENT COMPLET TERMINÉ")
    logger.info("Redémarre Uvicorn pour que les nouveaux modèles soient pris en compte.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
