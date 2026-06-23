import joblib
import numpy as np
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger("leadpilot.closing")

MODEL_PATH = Path(__file__).parent / "models" / "closing_model.pkl"

STAGE_RANK = {
    "Prospection": 0,
    "Qualification": 1,
    "Proposition": 2,
    "Négociation": 3,
    "Gagné": 4,
}

_cache = {}


def _load():
    """Charge le modèle (dict : model, features, source) avec cache."""
    mtime = MODEL_PATH.stat().st_mtime if MODEL_PATH.exists() else 0
    if _cache.get("mtime") != mtime:
        if not MODEL_PATH.exists():
            return None
        _cache["data"] = joblib.load(MODEL_PATH)
        _cache["mtime"] = mtime
    return _cache.get("data")


def model_info() -> dict:
    data = _load()
    if not data:
        return {"source": "none", "trained_at": None, "n_real": 0}
    return {
        "source": data.get("source", "synthetic"),
        "trained_at": data.get("trained_at"),
        "n_real": data.get("n_real", 0),
    }


def predict_closing(stage: str, value: float, lead_score: float,
                    created_at: datetime = None, risk: bool = False) -> int:
    """Probabilité de closing (0-100) prédite par XGBoost pour un deal."""
    if stage == "Perdu":
        return 0
    data = _load()
    if not data:
        # Repli : ancienne règle par étape si aucun modèle entraîné
        return {0: 20, 1: 40, 2: 60, 3: 80, 4: 100}.get(STAGE_RANK.get(stage, 0), 30)

    model    = data["model"]
    features = data.get("features", ["stage_rank", "value", "lead_score", "age_days", "risk"])

    age_days = 0.0
    if created_at:
        age_days = max(0.0, (datetime.utcnow() - created_at).days)

    values = {
        "stage_rank": STAGE_RANK.get(stage, 0),
        "value":      value or 0,
        "lead_score": lead_score or 50,
        "age_days":   age_days,
        "risk":       1 if risk else 0,
    }
    vec = np.array([[values[f] for f in features]])
    proba = float(model.predict_proba(vec)[0][1])
    return round(proba * 100)
