import os, sys, joblib, logging
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
DATABASE_URL = os.getenv("DATABASE_URL")
MODELS_DIR   = Path(__file__).parent / "models"
MODEL_PATH   = MODELS_DIR / "xgboost_model.pkl"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('scoring.log', encoding='utf-8')]
)
logger = logging.getLogger("leadpilot.scoring")

# Identiques a train_model.py
FEATURE_COLUMNS = [
    "has_email", "has_phone", "has_website", "has_address", "has_region",
    "email_quality", "email_confidence", "has_sector", "sector_score", "has_description", "company_type_score",
]

SOURCE_SCORES = {
    "linkedin_ceo":       1.0,
    "linkedin":           1.0,
    "startup_tunisia":    0.85,
    "google_maps":        0.75,
    "openstreetmap":      0.75,
    "manual":             0.70,
    "pages_jaunes_maroc": 0.65,
    "tunisieindex":       0.65,
    "tunidex":            0.65,
    "scraping":           0.65,
}

SECTOR_SCORES = {
    # Secteurs prioritaires (note maximale)
    "Culture & Musées":           1.0,
    "Culture & Patrimoine":       1.0,
    "Education & Formation":      1.0,
    "Informatique & Tech":        1.0,
    "Finance & Comptabilité":     0.90,
    "Finance & Comptabilite":     0.90,  # variante sans accent (legacy DB)
    "Santé":                      0.85,
    "Sante":                      0.85,  # variante sans accent (legacy DB)
    "Juridique":                  0.85,
    "Sécurité":                   0.85,
    "Marketing & Communication":  0.80,
    "Management & Conseil":       0.80,
    "Services aux entreprises":   0.75,
    "Architecture & Urbanisme":   0.75,
    "Immobilier":                 0.75,
    "Construction & BTP":         0.70,
    "Transport & Logistique":     0.70,
    "Logistique & Transport":     0.70,  # variante (legacy DB)
    "Commerce & Distribution":    0.65,
    "Industrie & Production":     0.65,
    "Agriculture & Alimentaire":  0.60,
    "Energie & Environnement":    0.60,
    "Tourisme & Loisirs":         0.55,
    "Tourisme & Voyages":         0.55,
    "Mode & Accessoires":         0.55,
    "Restauration & Hôtellerie":  0.55,
    "Restauration & Hotellerie":  0.55,  # variante sans accent (legacy DB)
}
EMAIL_ROLE_SCORES = {
    "ceo": 1.0, "founder": 0.95, "pdg": 0.90, "dg": 0.85,
    "director": 0.90, "directeur": 0.90,
    "sales": 0.85, "commercial": 0.85, "marketing": 0.80,
    "contact": 0.50, "info": 0.40, "admin": 0.30, "support": 0.25,
}
COMPANY_TYPE_SCORES = {
    "Startup":           1.0,
    "PME":               0.85,
    "Grande entreprise": 0.70,
    "Independant":       0.50,
    "Association":       0.30,
}

def get_company_type_score(company_type):
    if not company_type or pd.isna(company_type):
        return 0.60
    ct = str(company_type).strip()
    for key, score in COMPANY_TYPE_SCORES.items():
        if key.lower() in ct.lower():
            return score
    return 0.60
def get_email_quality(email):
    if not email or pd.isna(email): return 0.0
    local = str(email).split("@")[0].lower()
    for role, score in EMAIL_ROLE_SCORES.items():
        if role in local: return score
    return 0.60

def get_sector_score(sector):
    if not sector or pd.isna(sector): return np.nan
    return SECTOR_SCORES.get(str(sector), 0.50)

def extract_features(df):
    feat = pd.DataFrame(index=df.index)
    feat["has_email"]        = df["email"].notna().astype(float)
    feat["has_phone"]        = df["phone"].notna().astype(float)
    feat["has_website"]      = df["website"].notna().astype(float)
    feat["has_address"]      = df["address"].notna().astype(float)
    feat["has_region"]       = df["region"].notna().astype(float)
    feat["email_quality"]    = df["email"].apply(get_email_quality)
    feat["email_confidence"] = df["email_confidence"].apply(
        lambda x: float(x) / 100 if pd.notna(x) else np.nan
    )
    feat["has_sector"] = df["sector"].apply(
        lambda x: 1.0 if (pd.notna(x) and x != "Non specifie") else np.nan
    )
    feat["sector_score"]    = df["sector"].apply(get_sector_score)
    feat["has_description"] = df["description"].apply(
        lambda x: 1.0 if pd.notna(x) else np.nan
    )
    feat["company_type_score"] = df["company_type"].apply(get_company_type_score)
    return feat[FEATURE_COLUMNS]


def score_leads(rescore_all=False):
    logger.info("LeadPilot - Scoring XGBoost")
    logger.info("=" * 50)

    if not MODEL_PATH.exists():
        logger.error("Modele non trouve. Lance : python -m app.train_model")
        sys.exit(1)

    data       = joblib.load(MODEL_PATH)
    model      = data["model"]
    metrics    = data.get("metrics", {})
    trained_at = data.get("trained_at", "?")
    logger.info(f"Modele charge ({trained_at})")
    logger.info(f"   MAE={metrics.get('mae',0):.2f}  R2={metrics.get('r2',0):.3f}")

    engine = create_engine(DATABASE_URL)

    if rescore_all:
        query = """
            SELECT id, email, phone, website, address, region,
                   sector, description, email_confidence,
                   reviews_count, reviews_average, source,company_type 
            FROM leads
            WHERE enriched = TRUE
        """
        logger.info("Mode : re-score TOUS les leads enrichis")
    else:
        query = """
            SELECT id, email, phone, website, address, region,
                   sector, description, email_confidence,
                   reviews_count, reviews_average, source,company_type 
            FROM leads
            WHERE enriched = TRUE
            AND (lead_score IS NULL OR lead_score = 0)
        """
        logger.info("Mode : score les nouveaux leads enrichis")

    df = pd.read_sql(query, engine)
    logger.info(f"   {len(df)} leads a scorer")

    if len(df) == 0:
        logger.info("Tous les leads sont deja scores !")
        return

    X      = extract_features(df)
    scores = np.clip(model.predict(X), 0, 100).round(2)

    logger.info(f"   Score moyen  : {scores.mean():.1f}")
    logger.info(f"   Score median : {np.median(scores):.1f}")
    logger.info(f"   Score max    : {scores.max():.1f}")
    logger.info(f"   Score min    : {scores.min():.1f}")

    updated = 0
    with engine.connect() as conn:
        for i, (_, row) in enumerate(df.iterrows()):
            conn.execute(text("""
                UPDATE leads SET lead_score=:score, scored_at=:ts WHERE id=:id
            """), {"score": float(scores[i]), "ts": datetime.utcnow(), "id": int(row["id"])})
            updated += 1
            if updated % 500 == 0:
                conn.commit()
                logger.info(f"   {updated}/{len(df)} scores...")
        conn.commit()

    cold = int((scores < 33).sum())
    warm = int(((scores >= 33) & (scores < 66)).sum())
    hot  = int((scores >= 66).sum())

    logger.info(f"\n{updated} leads scores")
    logger.info(f"   Froid (<33)  : {cold}  ({cold/len(df)*100:.1f}%)")
    logger.info(f"   Tiede (33-66): {warm}  ({warm/len(df)*100:.1f}%)")
    logger.info(f"   Chaud (>66)  : {hot}   ({hot/len(df)*100:.1f}%)")

def get_feature_importance() -> list:
    """Retourne l'importance des features XGBoost triée par ordre décroissant."""
    if not MODEL_PATH.exists():
        return []
    try:
        data  = joblib.load(MODEL_PATH)
        model = data["model"]
        scores = model.feature_importances_
        labels = {
            "has_email":          "Email présent",
            "has_phone":          "Téléphone présent",
            "has_website":        "Site web présent",
            "has_address":        "Adresse présente",
            "has_region":         "Région présente",
            "email_quality":      "Qualité email (rôle)",
            "email_confidence":   "Confiance email Hunter",
            "has_sector":         "Secteur renseigné",
            "sector_score":       "Score secteur (B2B)",
            "has_description":    "Description IA présente",
            "company_type_score": "Type société",
        }
        result = []
        for feat, imp in zip(FEATURE_COLUMNS, scores):
            result.append({
                "feature": labels.get(feat, feat),
                "importance": round(float(imp) * 100, 1),
            })
        return sorted(result, key=lambda x: x["importance"], reverse=True)
    except Exception as e:
        logger.error(f"Erreur feature importance: {e}")
        return []


if __name__ == "__main__":
    score_leads("--all" in sys.argv)