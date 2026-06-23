import os
import numpy as np
import joblib
from pathlib import Path
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score

np.random.seed(42)
N = 6000

MODELS_DIR = Path(__file__).parent.parent / "app" / "models"
MODELS_DIR.mkdir(exist_ok=True)
OUT = MODELS_DIR / "closing_model.pkl"

STAGE_BASE = [0.15, 0.32, 0.52, 0.74, 0.95]  # Prospection -> Gagné

rows_X, rows_y = [], []
for _ in range(N):
    stage_rank = np.random.randint(0, 5)
    value      = np.random.uniform(5000, 100000)
    lead_score = np.random.uniform(10, 95)
    age_days   = np.random.uniform(0, 90)
    risk       = 1 if np.random.random() < 0.15 else 0

    p = STAGE_BASE[stage_rank]
    p += (lead_score - 50) / 100 * 0.25
    p -= (value / 100000) * 0.15
    p -= (age_days / 90) * 0.20
    p -= risk * 0.25
    p += np.random.normal(0, 0.05)
    p = float(np.clip(p, 0.02, 0.98))

    won = int(np.random.binomial(1, p))
    rows_X.append([stage_rank, value, lead_score, age_days, risk])
    rows_y.append(won)

X = np.array(rows_X)
y = np.array(rows_y)

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = XGBClassifier(
    n_estimators=250, max_depth=5, learning_rate=0.08,
    subsample=0.9, colsample_bytree=0.9, eval_metric="logloss", random_state=42,
)
model.fit(X_train, y_train)

pred = model.predict(X_test)
proba = model.predict_proba(X_test)[:, 1]
acc = accuracy_score(y_test, pred)
auc = roc_auc_score(y_test, proba)

print(f"Accuracy : {acc:.4f}")
print(f"AUC      : {auc:.4f}")
print("Importance features [stage, value, lead_score, age_days, risk]:")
print(np.round(model.feature_importances_, 3))

from datetime import datetime
joblib.dump({
    "model": model,
    "features": ["stage_rank", "value", "lead_score", "age_days", "risk"],
    "source": "synthetic",
    "trained_at": datetime.utcnow().isoformat(),
    "n_real": 0,
}, OUT)
print(f"Modele sauvegarde : {OUT}")
