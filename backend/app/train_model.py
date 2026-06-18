import os, sys, joblib
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine
from dotenv import load_dotenv
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_absolute_error, r2_score
import xgboost as xgb

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
DATABASE_URL = os.getenv("DATABASE_URL")
MODELS_DIR   = Path(__file__).parent / "models"
MODELS_DIR.mkdir(exist_ok=True)

# SCORES DE REFERENCE
SOURCE_SCORES = {
    "linkedin": 1.0, "startup_tunisia": 0.85,
    "google_maps": 0.75, "tunisieindex": 0.65,
    "manual": 0.70, "scraping": 0.65,
}

SECTOR_SCORES = {
    "Informatique & Tech": 1.0, "Finance & Comptabilite": 0.90,
    "Sante": 0.85, "Juridique": 0.85,
    "Marketing & Communication": 0.80, "Services aux entreprises": 0.75,
    "Immobilier": 0.75, "Construction & BTP": 0.70,
    "Transport & Logistique": 0.70, "Education & Formation": 0.65,
    "Commerce & Distribution": 0.65, "Industrie & Production": 0.65,
    "Agriculture & Alimentaire": 0.60, "Energie & Environnement": 0.60,
    "Restauration & Hotellerie": 0.55,
}

# Scores selon type entreprise (critere societe)
# Startup = cible ideale pour un SaaS B2B
# PME = coeur de cible
# Grande entreprise = cycle de vente long
# Independant = budget limite
COMPANY_TYPE_SCORES = {
    "Startup":           1.0,
    "PME":               0.85,
    "Grande entreprise": 0.70,
    "Independant":       0.50,
    "Association":       0.30,
}

EMAIL_ROLE_SCORES = {
    "ceo": 1.0, "founder": 0.95, "pdg": 0.90, "dg": 0.85,
    "director": 0.90, "directeur": 0.90,
    "sales": 0.85, "commercial": 0.85, "marketing": 0.80,
    "contact": 0.50, "info": 0.40, "admin": 0.30, "support": 0.25,
}

def get_email_quality(email):
    if not email or pd.isna(email): return 0.0
    local = str(email).split("@")[0].lower()
    for role, score in EMAIL_ROLE_SCORES.items():
        if role in local: return score
    return 0.60

def get_source_score(source):
    if not source or pd.isna(source): return 0.65
    for key, score in SOURCE_SCORES.items():
        if key in str(source).lower(): return score
    return 0.65

def get_sector_score(sector):
    if not sector or pd.isna(sector): return np.nan
    return SECTOR_SCORES.get(str(sector), 0.50)

def get_company_type_score(company_type):
    if not company_type or pd.isna(company_type): return 0.60
    ct = str(company_type).strip()
    for key, score in COMPANY_TYPE_SCORES.items():
        if key.lower() in ct.lower(): return score
    return 0.60


# FEATURES — ce que XGBoost voit
# Inclut maintenant company_type_score (critere societe)
FEATURE_COLUMNS = [
    # Contact (brutes)
    "has_email",
    "has_phone",
    "has_website",
    "has_address",
    "has_region",
    # Qualite email
    "email_quality",
    # Enrichissement IA
    "email_confidence",
    "has_sector",
    "sector_score",
    "has_description",
    # Type entreprise (critere societe) — NOUVEAU
    "company_type_score",
]


# LABEL — score commercial 0-100
# Criteres demandes par la societe :
#   Secteur d activite sector_score dans label
#   Type entreprise company_type_score dans label
#   Presence digitale has_website dans features
#   Coordonnees disponibles has_email/phone dans features
#   Niveau d activite reviews dans label
#   Localisation has_region dans features
# SEPARATION label/features :
#   Label utilise  : source, reviews, sector_score, company_type_score
#   Features       : has_email, has_phone, has_website, has_address,
#                    email_quality, email_confidence, has_sector,
#                    sector_score, has_description, company_type_score
# Note : sector_score et company_type_score sont dans les deux
# mais reviews reste absent des features -> vrai apprentissage ML
def generate_score_target(df):
    """
    Score commercial 0-100 selon criteres societe.

    Source(20) + Reviews(25) + Secteur(25) + CompanyType(20) + Completude contact(10) = 100

    Criteres societe couverts :
    - Secteur d activite        -> sector_score (25 pts)
    - Type entreprise           -> company_type_score (20 pts)
    - Niveau d activite         -> reviews (25 pts — absent des features)
    - Presence digitale         -> dans features (has_website)
    - Coordonnees disponibles   -> dans features (has_email, has_phone)
    - Localisation              -> dans features (has_region)
    """
    scores = pd.Series(0.0, index=df.index)

    # 1. Source (20 pts) — credibilite de la source
    scores += df["source"].apply(get_source_score) * 20

    # 2. Reviews Google (25 pts) — seule variable absente des features
    has_reviews = df["reviews_count"].notna() & (df["reviews_count"] > 0)
    reviews = df["reviews_count"].fillna(0).clip(0, 200) / 200
    avg     = df["reviews_average"].fillna(0) / 5
    scores += has_reviews * (reviews * 12.5 + avg * 12.5)

    # 3. Secteur d activite (25 pts) — critere societe
    sector_pts = df["sector"].apply(
        lambda s: get_sector_score(s) if pd.notna(s) else 0.50
    )
    scores += sector_pts * 25

    # 4. Type entreprise (20 pts) — critere societe
    scores += df["company_type"].apply(get_company_type_score) * 20

    # 5. Completude contact (10 pts) — joignabilite basique
    completeness = (
        df["email"].notna().astype(int) +
        df["phone"].notna().astype(int)
    ) / 2
    scores += completeness * 10

    return scores.clip(0, 100).round(2)


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
    feat["sector_score"]      = df["sector"].apply(get_sector_score)
    feat["has_description"]   = df["description"].apply(
        lambda x: 1.0 if pd.notna(x) else np.nan
    )
    feat["company_type_score"] = df["company_type"].apply(get_company_type_score)
    return feat[FEATURE_COLUMNS]


def train():
    print("\n LeadPilot - Entrainement XGBoost (criteres societe integres)")
    print("=" * 65)
    print("\n Label = Source(20) + Reviews(25) + Secteur(25) + CompanyType(20) + Contact(10)")
    print(" Criteres societe : secteur, type entreprise, activite, coordonnees\n")

    engine = create_engine(DATABASE_URL)

    print(" Chargement des donnees...")
    query = """
        SELECT id, email, phone, website, address, region,
               sector, description, email_confidence,
               reviews_count, reviews_average, source,
               company_type, enriched
        FROM leads
    """
    df = pd.read_sql(query, engine)
    total    = len(df)
    enriched = int(df["enriched"].sum())

    print(f"   Total leads    : {total}")
    print(f"   Leads enrichis : {enriched} ({enriched/total*100:.1f}%)")

    print(f"\n   Repartition par source :")
    for src, grp in df.groupby("source"):
        has_rev = (grp["reviews_count"].notna() & (grp["reviews_count"] > 0)).sum()
        print(f"      {str(src):<22} : {len(grp):>5} leads | {has_rev:>4} avec reviews")

    print(f"\n   Repartition par company_type :")
    ct_counts = df["company_type"].fillna("NULL").value_counts()
    for ct, cnt in ct_counts.items():
        score = get_company_type_score(ct if ct != "NULL" else None)
        print(f"      {str(ct):<22} : {cnt:>5} leads | score {score:.2f}")

    if total < 50:
        print("   Pas assez de donnees"); sys.exit(1)

    print("\n Calcul des labels (criteres societe)...")
    y = generate_score_target(df)

    print(f"   Score moyen  : {y.mean():.1f}")
    print(f"   Score median : {y.median():.1f}")
    print(f"   Score min    : {y.min():.1f}")
    print(f"   Score max    : {y.max():.1f}")
    print(f"\n   Distribution :")
    print(f"      Froid (<33)  : {(y<33).sum():>5} ({(y<33).mean()*100:.1f}%)")
    print(f"      Tiede (33-66): {((y>=33)&(y<66)).sum():>5} ({((y>=33)&(y<66)).mean()*100:.1f}%)")
    print(f"      Chaud (>66)  : {(y>=66).sum():>5} ({(y>=66).mean()*100:.1f}%)")

    print(f"\n   Score moyen par source :")
    for src, grp in df.groupby("source"):
        print(f"      {str(src):<22} : {y[grp.index].mean():.1f} pts")

    print("\n Extraction features...")
    X = extract_features(df)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    print(f"   Split : {len(X_train)} train / {len(X_test)} test")

    print("\n Entrainement XGBoost...")
    model = xgb.XGBRegressor(
        n_estimators=300, max_depth=5, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, min_child_weight=10,
        random_state=42, n_jobs=-1,
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    print("\n Evaluation...")
    y_pred = np.clip(model.predict(X_test), 0, 100)
    mae    = mean_absolute_error(y_test, y_pred)
    r2     = r2_score(y_test, y_pred)
    cv     = cross_val_score(model, X_train, y_train, cv=5, scoring="r2")

    print(f"   MAE            : {mae:.2f} pts")
    print(f"   R2 (test)      : {r2:.3f}")
    print(f"   CV R2 (train)  : {cv.mean():.3f} +/- {cv.std():.3f}")
    print(f"   CV par fold    : {[round(s,3) for s in cv]}")

    if r2 > 0.95:
        print("   ATTENTION : R2 trop eleve")
    elif r2 > 0.5:
        print("   EXCELLENT : modele bien calibre")
    elif r2 > 0.3:
        print("   OK : R2 acceptable")
    else:
        print("   R2 faible — normal avec donnees heterogenes")

    print("\n Importance des features :")
    enrichies = ["email_confidence", "has_sector", "sector_score",
                 "has_description", "company_type_score"]
    imp = pd.DataFrame({
        "feature": FEATURE_COLUMNS,
        "importance": model.feature_importances_
    }).sort_values("importance", ascending=False)

    for _, row in imp.iterrows():
        bar = "=" * int(row["importance"] * 40)
        tag = "(enrichie)" if row["feature"] in enrichies else "(brute)   "
        print(f"   {tag} {row['feature']:<24} {bar} {row['importance']:.3f}")

    model_path = MODELS_DIR / "xgboost_model.pkl"
    joblib.dump({
        "model": model,
        "feature_columns": FEATURE_COLUMNS,
        "trained_at": datetime.utcnow().isoformat(),
        "n_samples": total, "n_enriched": enriched,
        "label_basis": "source(20)+reviews(25)+secteur(25)+company_type(20)+contact(10)",
        "metrics": {
            "mae": float(mae), "r2": float(r2),
            "cv_r2": float(cv.mean()), "cv_std": float(cv.std())
        }
    }, model_path)

    print(f"\n Modele sauvegarde : {model_path}")
    print(f"   MAE={mae:.2f}  R2={r2:.3f}  CV={cv.mean():.3f}")
    return model

if __name__ == "__main__":
    train()