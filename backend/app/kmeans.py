import os
import sys
import joblib
import numpy as np
import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
MODELS_DIR   = Path(__file__).parent / "models"
MODELS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('kmeans.log', encoding='utf-8')
    ]
)
logger = logging.getLogger("leadpilot.kmeans")



KMEANS_FEATURES = [
    "lead_score",  
]

SEGMENT_NAMES = {
    "highest":  "Chaud",       # leads avec le meilleur score
    "high":     "Prêts à Acheter",  #  bon score
    "low":      "Froid",       # faible score
    "risk":     "À Risque",    #  données manquantes
}



SECTOR_SCORES = {
    "Informatique & Tech": 1.0, "Finance & Comptabilité": 0.90,
    "Santé": 0.85, "Juridique": 0.85,
    "Marketing & Communication": 0.80, "Services aux entreprises": 0.75,
    "Immobilier": 0.75, "Construction & BTP": 0.70,
    "Transport & Logistique": 0.70, "Education & Formation": 0.65,
    "Commerce & Distribution": 0.65, "Industrie & Production": 0.65,
    "Agriculture & Alimentaire": 0.60, "Energie & Environnement": 0.60,
    "Restauration & Hôtellerie": 0.55,
}

COMPANY_TYPE_SCORES = {
    "Startup": 1.0, "PME": 0.85, "Grande entreprise": 0.70,
    "Indépendant": 0.50, "Association": 0.30,
}


def load_data(engine) -> pd.DataFrame:
    """Charge les leads scorés depuis PostgreSQL"""
    query = """
        SELECT id, lead_score, email, phone, website,
               reviews_count, sector, company_type
        FROM leads
        WHERE lead_score IS NOT NULL
        AND lead_score > 0
    """
    df = pd.read_sql(query, engine)
    logger.info(f"   {len(df)} leads scorés chargés")
    return df


def prepare_features(df: pd.DataFrame) -> np.ndarray:
    """
    Prépare les features pour K-Means.
    IMPORTANT : K-Means utilise des distances euclidiennes,
    donc toutes les features doivent être sur la même échelle.
    StandardScaler normalise chaque feature (moyenne=0, écart-type=1).
    """
    features = pd.DataFrame(index=df.index)
    features["lead_score"] = df["lead_score"] / 100

    return features[KMEANS_FEATURES].values



def name_clusters(df: pd.DataFrame, n_clusters: int = 4) -> dict:
    """
    K-Means donne des numéros (0, 1, 2, 3) aux clusters.
    On les traduit en noms business selon le score moyen.

    Exemple :
      Cluster 2 score moyen = 78 "Chaud"
      Cluster 0 score moyen = 45 "Tiède"
      Cluster 3 score moyen = 22 "Froid"
      Cluster 1 score moyen = 31, email=0% "À Risque"
    """
    # Score moyen et taux email par cluster
    cluster_stats = df.groupby("cluster").agg(
        score_mean=("lead_score", "mean"),
        email_rate=("email", lambda x: x.notna().mean()),
        count=("lead_score", "count")
    ).reset_index()

    cluster_stats = cluster_stats.sort_values("score_mean", ascending=False)

    mapping = {}

    if n_clusters == 4:
        clusters_sorted = cluster_stats["cluster"].tolist()

        # Meilleur score Chaud
        mapping[clusters_sorted[0]] = "Chaud"
        # Deuxième Prêts à Acheter
        mapping[clusters_sorted[1]] = "Prêts à Acheter"

        # Entre les deux restants :
        # celui avec le moins d'emails À Risque
        remaining = cluster_stats[cluster_stats["cluster"].isin(clusters_sorted[2:])]
        risk_cluster = remaining.sort_values("email_rate").iloc[0]["cluster"]
        cold_cluster = remaining[remaining["cluster"] != risk_cluster].iloc[0]["cluster"]

        mapping[risk_cluster] = "À Risque"
        mapping[cold_cluster] = "Froid"

    else:
        # Pour k != 4 : nommage simple par rang de score
        labels = ["Chaud", "Tiède", "Froid", "À Risque"]
        for i, cluster_id in enumerate(cluster_stats["cluster"].tolist()):
            mapping[cluster_id] = labels[min(i, len(labels)-1)]

    return mapping


# ENTRAÎNEMENT K-MEANS

def run_kmeans():
    logger.info("\n LeadPilot — Segmentation K-Means")
    logger.info("=" * 50)

    engine = create_engine(DATABASE_URL)

    # 1. Charger les données
    logger.info("\n Chargement des leads scorés...")
    df = load_data(engine)

    if len(df) < 50:
        logger.error(f" Pas assez de leads scorés ({len(df)})")
        logger.error("   Lance d'abord : python -m app.scoring")
        sys.exit(1)

    # 2. Préparer les features
    logger.info("\n Préparation des features...")
    X = prepare_features(df)

    # Normalisation (obligatoire pour K-Means)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # 3. Trouver le meilleur k (si on veut optimiser)
    # On fixe k=4 selon le cahier des charges :
    # Chaud / Tiède / Froid / À Risque
    n_clusters = 4

    # 4. Entraîner K-Means
    logger.info(f"\n Entraînement K-Means (k={n_clusters})...")
    kmeans = KMeans(
        n_clusters=n_clusters,
        init="k-means++",    # initialisation intelligente
        n_init=10,           # 10 essais, on garde le meilleur
        max_iter=300,
        random_state=42
    )
    cluster_labels = kmeans.fit_predict(X_scaled)
    df["cluster"]  = cluster_labels

    # 5. Évaluation qualité des clusters (avant correction)
    sil_raw = silhouette_score(X_scaled, cluster_labels)
    logger.info(f"\n Silhouette brut (K-Means pur) : {sil_raw:.3f}")

    # 6. Nommer les clusters
    logger.info("\n Attribution des noms business...")
    cluster_to_segment = name_clusters(df, n_clusters)
    df["segment"] = df["cluster"].map(cluster_to_segment)

    # En 1D sur lead_score, K-Means produit des tranches ordonnées —
    # la cohérence score segment est garantie mathématiquement.
    sil_score = sil_raw
    logger.info(f" Silhouette : {sil_score:.3f}")
    logger.info("   (1.0 = clusters parfaits | 0.0 = clusters mélangés)")

    # 7. Afficher les statistiques par segment
    logger.info("\n Statistiques par segment :")
    stats = df.groupby("segment").agg(
        count=("lead_score", "count"),
        score_moyen=("lead_score", "mean"),
        score_min=("lead_score", "min"),
        score_max=("lead_score", "max"),
    ).round(1)

    for segment, row in stats.iterrows():
        icon = {"Chaud": " ", "Prêts à Acheter": " ", "Froid": " ", "À Risque": " "}.get(segment, "•")
        logger.info(
            f"   {icon} {segment:<12} : {int(row['count']):>5} leads | "
            f"score {row['score_moyen']:.1f} "
            f"[{row['score_min']:.0f}-{row['score_max']:.0f}]"
        )

    # 8. Mettre à jour PostgreSQL (batch par 500)
    logger.info("\n Mise à jour PostgreSQL...")
    now = datetime.utcnow()
    rows_list = df[["id", "segment"]].values.tolist()
    batch_size = 500
    updated = 0

    with engine.connect() as conn:
        for i in range(0, len(rows_list), batch_size):
            batch = rows_list[i:i + batch_size]
            # CASE WHEN id=X THEN 'segment' batch update
            ids = [int(r[0]) for r in batch]
            cases = " ".join(f"WHEN {int(r[0])} THEN '{r[1]}'" for r in batch)
            conn.execute(text(f"""
                UPDATE leads
                SET segment = CASE id {cases} END,
                    segmented_at = :ts
                WHERE id IN ({','.join(str(i) for i in ids)})
            """), {"ts": now})
            conn.commit()
            updated += len(batch)
            logger.info(f" {updated}/{len(df)} leads mis à jour...")

    # 9. Sauvegarder le modèle K-Means
    model_path = MODELS_DIR / "kmeans_model.pkl"
    joblib.dump({
        "kmeans":            kmeans,
        "scaler":            scaler,
        "cluster_to_segment": cluster_to_segment,
        "feature_columns":   KMEANS_FEATURES,
        "trained_at":        datetime.utcnow().isoformat(),
        "n_samples":         len(df),
        "silhouette_score":  float(sil_score),   # après correct_segment
        "silhouette_raw":    float(sil_raw),     # K-Means pur
    }, model_path)

    logger.info(f"\nK-Means terminé !")
    logger.info(f"   {updated} leads segmentés")
    logger.info(f"   Modèle sauvegardé : {model_path}")
    logger.info(f"   Silhouette brut  : {sil_raw:.3f}")
    logger.info(f"   Silhouette final : {sil_score:.3f}")


if __name__ == "__main__":
    run_kmeans()
