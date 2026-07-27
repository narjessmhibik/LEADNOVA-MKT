import os
import sys
import joblib
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import r2_score, mean_absolute_error

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
MODELS_DIR   = Path(__file__).parent.parent / "app" / "models"
MIN_OPENS    = 200   # seuil minimum d'ouvertures réelles pour utiliser ce script

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("leadpilot.timing_real")

JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def load_real_data(engine) -> pd.DataFrame:
    """
    Lit depuis la DB :
      - emails ouverts  (ouvert=1) avec heure/jour de l'ouverture
      - emails envoyés non ouverts (ouvert=0) avec heure/jour de l'envoi
    Retourne un DataFrame avec colonnes :
      heure, jour, segment, secteur, ouvert
    """
    # Ouvertures réelles
    opens_query = """
        SELECT
            EXTRACT(HOUR FROM email_opened_at)::int  AS heure,
            -- DOW PostgreSQL : 0=dimanche ... 6=samedi -> on corrige vers 0=lundi
            ((EXTRACT(DOW FROM email_opened_at)::int + 6) % 7) AS jour,
            segment,
            sector  AS secteur,
            1       AS ouvert
        FROM leads
        WHERE email_opened    = TRUE
          AND email_opened_at IS NOT NULL
          AND segment         IS NOT NULL
          AND sector          IS NOT NULL
    """

    # Emails envoyés mais pas ouverts (négatifs)
    not_opened_query = """
        SELECT
            EXTRACT(HOUR FROM email_sent_at)::int  AS heure,
            ((EXTRACT(DOW FROM email_sent_at)::int + 6) % 7) AS jour,
            segment,
            sector  AS secteur,
            0       AS ouvert
        FROM leads
        WHERE email_sent      = TRUE
          AND email_sent_at   IS NOT NULL
          AND email_opened    = FALSE
          AND segment         IS NOT NULL
          AND sector          IS NOT NULL
    """

    df_opens     = pd.read_sql(opens_query,     engine)
    df_not_opens = pd.read_sql(not_opened_query, engine)

    logger.info(f"Ouvertures réelles    : {len(df_opens)}")
    logger.info(f"Envoyés non ouverts   : {len(df_not_opens)}")

    df = pd.concat([df_opens, df_not_opens], ignore_index=True)
    logger.info(f"Dataset total         : {len(df)} lignes")
    logger.info(f"Taux ouverture réel   : {df['ouvert'].mean():.1%}")
    return df


def compute_p_real(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcule le taux d'ouverture réel par combinaison (heure, jour, segment, secteur).
    Chaque ligne originale reçoit ce taux comme label p_real.
    Lisse avec un prior bayésien (prior=0.25, poids=10) pour éviter
    que 1 seul envoi donne p=1.0 ou p=0.0.
    """
    PRIOR      = 0.25   # taux d'ouverture moyen supposé a priori
    PRIOR_WEIGHT = 10   # équivalent à 10 observations fictives

    group = df.groupby(["heure", "jour", "segment", "secteur"])["ouvert"]
    counts = group.count().rename("n")
    sums   = group.sum().rename("s")
    stats  = pd.concat([counts, sums], axis=1).reset_index()

    # Lissage bayésien : (somme + prior*poids) / (n + poids)
    stats["p_real"] = (stats["s"] + PRIOR * PRIOR_WEIGHT) / (stats["n"] + PRIOR_WEIGHT)

    df = df.merge(stats[["heure", "jour", "segment", "secteur", "p_real", "n"]],
                  on=["heure", "jour", "segment", "secteur"],
                  how="left")

    logger.info(f"p_real moyen  : {df['p_real'].mean():.3f}")
    logger.info(f"p_real min    : {df['p_real'].min():.3f}")
    logger.info(f"p_real max    : {df['p_real'].max():.3f}")
    return df


def train(df: pd.DataFrame):
    # Encodage catégories
    le_segment = LabelEncoder()
    le_secteur = LabelEncoder()

    df["segment_enc"] = le_segment.fit_transform(df["segment"])
    df["secteur_enc"] = le_secteur.fit_transform(df["secteur"])

    logger.info(f"Segments : {list(le_segment.classes_)}")
    logger.info(f"Secteurs : {list(le_secteur.classes_)}")

    # Features et label
    FEATURES = ["heure", "jour", "segment_enc", "secteur_enc"]
    X = df[FEATURES]
    y = df["p_real"]

    # Split 80/20
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    logger.info(f"Train : {len(X_train)} | Test : {len(X_test)}")

    # Mêmes hyperparamètres que le modèle synthétique
    model = RandomForestRegressor(
        n_estimators=300,
        max_depth=12,
        min_samples_split=15,
        min_samples_leaf=8,
        max_features="sqrt",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    # Métriques
    y_pred = model.predict(X_test)
    r2   = r2_score(y_test, y_pred)
    mae  = mean_absolute_error(y_test, y_pred)
    corr = np.corrcoef(y_test, y_pred)[0, 1]

    logger.info("=== Métriques ===")
    logger.info(f"R2          : {r2:.4f}")
    logger.info(f"MAE         : {mae:.4f}")
    logger.info(f"Corrélation : {corr:.4f}")

    cv_scores = cross_val_score(model, X, y, cv=5, scoring="r2", n_jobs=-1)
    logger.info(f"CV R2 : {cv_scores.mean():.4f} +/- {cv_scores.std():.4f}")

    # Importance features
    logger.info("=== Importance des features ===")
    for feat, imp in sorted(zip(FEATURES, model.feature_importances_), key=lambda x: -x[1]):
        bar = "|" * int(imp * 60)
        logger.info(f"  {feat:<15} {imp:.4f}  {bar}")

    # Meilleurs créneaux par segment
    logger.info("=== Meilleurs créneaux par segment ===")
    for seg in le_segment.classes_:
        seg_enc = le_segment.transform([seg])[0]
        best = None
        for sec in le_secteur.classes_:
            sec_enc = le_secteur.transform([sec])[0]
            for h in range(6, 22):
                for d in range(0, 7):
                    score = model.predict([[h, d, seg_enc, sec_enc]])[0]
                    if best is None or score > best[0]:
                        best = (score, h, d, sec)
        logger.info(f"  {seg:<22} -> {JOURS[best[2]]} {best[1]:02d}h  score={best[0]:.3f}  [{best[3]}]")

    return model, le_segment, le_secteur


def save(model, le_segment, le_secteur, n_opens: int):
    MODELS_DIR.mkdir(exist_ok=True)
    joblib.dump(model,      MODELS_DIR / "timing_model.pkl")
    joblib.dump(le_segment, MODELS_DIR / "timing_le_segment.pkl")
    joblib.dump(le_secteur, MODELS_DIR / "timing_le_secteur.pkl")

    meta = {
        "trained_at":   datetime.utcnow().isoformat(),
        "source":       "real",
        "n_opens":      n_opens,
        "min_opens":    MIN_OPENS,
    }
    joblib.dump(meta, MODELS_DIR / "timing_meta.pkl")

    logger.info(f"Modèles sauvegardés dans : {MODELS_DIR}")
    logger.info("  timing_model.pkl")
    logger.info("  timing_le_segment.pkl")
    logger.info("  timing_le_secteur.pkl")
    logger.info("  timing_meta.pkl")


def main():
    logger.info("=" * 60)
    logger.info("LeadPilot — Réentraînement timing sur données RÉELLES")
    logger.info("=" * 60)

    if not DATABASE_URL:
        logger.error("DATABASE_URL manquant dans .env")
        sys.exit(1)

    engine = create_engine(DATABASE_URL)
    df = load_real_data(engine)
    n_opens = int((df["ouvert"] == 1).sum())

    if n_opens < MIN_OPENS:
        logger.error(
            f"Pas assez d'ouvertures réelles : {n_opens} < {MIN_OPENS}. "
            "Attendez d'avoir envoyé plus de campagnes."
        )
        sys.exit(1)

    df = compute_p_real(df)
    model, le_segment, le_secteur = train(df)
    save(model, le_segment, le_secteur, n_opens)

    logger.info(f"\nRéentraînement terminé sur {n_opens} ouvertures réelles.")
    logger.info("Redémarre Uvicorn pour que le nouveau modèle soit pris en compte.")


if __name__ == "__main__":
    main()
