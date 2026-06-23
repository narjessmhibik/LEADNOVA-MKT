import joblib
import numpy as np
from pathlib import Path
from datetime import datetime
import logging
from sqlalchemy import text
from app.database import SyncSessionLocal

logger = logging.getLogger("leadpilot.closing_retrain")

MODEL_PATH = Path(__file__).parent / "models" / "closing_model.pkl"
THRESHOLD = 40  # nb minimum de deals clôturés pour basculer sur les données réelles


def count_closed_deals(db) -> tuple:
    """Retourne (total_clos, gagnes, perdus)."""
    row = db.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE stage IN ('Gagné', 'Perdu')) AS total,
            COUNT(*) FILTER (WHERE stage = 'Gagné')             AS won,
            COUNT(*) FILTER (WHERE stage = 'Perdu')             AS lost
        FROM opportunities
    """)).fetchone()
    return row.total or 0, row.won or 0, row.lost or 0


def retrain_closing_on_real() -> dict:
    """
    Réentraîne le modèle de closing sur les vrais deals clôturés si le seuil
    est atteint (et si les deux classes Gagné/Perdu sont présentes).
    Sinon, ne touche pas au modèle synthétique.
    """
    db = SyncSessionLocal()
    try:
        total, won, lost = count_closed_deals(db)
        if total < THRESHOLD or won < 5 or lost < 5:
            logger.info(f"[CLOSING] Pas assez de données réelles ({total}/{THRESHOLD}, "
                        f"gagnés={won}, perdus={lost}) — modèle synthétique conservé")
            return {"retrained": False, "total": total, "won": won, "lost": lost}

        from xgboost import XGBClassifier

        rows = db.execute(text("""
            SELECT o.value, o.created_at, o.risk, o.stage,
                   COALESCE(l.lead_score, 50) AS lead_score
            FROM opportunities o
            LEFT JOIN leads l ON l.id = o.lead_id
            WHERE o.stage IN ('Gagné', 'Perdu')
        """)).fetchall()

        X, y = [], []
        now = datetime.utcnow()
        for r in rows:
            age = max(0.0, (now - r.created_at).days) if r.created_at else 0.0
            X.append([r.value or 0, r.lead_score or 50, age, 1 if r.risk else 0])
            y.append(1 if r.stage == "Gagné" else 0)

        X, y = np.array(X), np.array(y)
        model = XGBClassifier(n_estimators=150, max_depth=4, learning_rate=0.1,
                              eval_metric="logloss", random_state=42)
        model.fit(X, y)

        joblib.dump({
            "model": model,
            # NB : pas de "stage_rank" — pour les deals clôturés, l'étape = le résultat
            "features": ["value", "lead_score", "age_days", "risk"],
            "source": "real",
            "trained_at": now.isoformat(),
            "n_real": total,
        }, MODEL_PATH)

        logger.info(f"[CLOSING] Réentraîné sur {total} deals réels (gagnés={won}, perdus={lost})")
        return {"retrained": True, "total": total, "won": won, "lost": lost}
    except Exception as e:
        logger.error(f"[CLOSING] Erreur réentraînement: {e}")
        return {"retrained": False, "error": str(e)}
    finally:
        db.close()
