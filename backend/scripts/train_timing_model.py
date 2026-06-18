import pandas as pd
import numpy as np
import joblib
import os
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import r2_score, mean_absolute_error

# Chargement donnees 
data_path = os.path.join(os.path.dirname(__file__), "..", "data", "timing_data.csv")
df = pd.read_csv(data_path)
print(f"Donnees chargees : {len(df)} lignes")
print(f"Score moyen      : {df['p_theo'].mean():.3f}\n")

# Encodage 
le_segment = LabelEncoder()
le_secteur = LabelEncoder()

df["segment_enc"] = le_segment.fit_transform(df["segment"])
df["secteur_enc"] = le_secteur.fit_transform(df["secteur"])

print("Segments :", list(le_segment.classes_))
print("Secteurs :", list(le_secteur.classes_))
print()

# Features et target (score continu) 
FEATURES = ["heure", "jour", "segment_enc", "secteur_enc"]
X = df[FEATURES]
y = df["p_theo"]   # score continu 0-1, pas 0/1 binaire

# Split 80/20 
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)
print(f"Train : {len(X_train)} | Test : {len(X_test)}\n")

# Entrainement RandomForestRegressor 
print("Entrainement Random Forest Regressor...")
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
print("Entrainement termine.\n")

# Evaluation 
y_pred = model.predict(X_test)

r2  = r2_score(y_test, y_pred)
mae = mean_absolute_error(y_test, y_pred)
corr = np.corrcoef(y_test, y_pred)[0, 1]

print("=== Metriques ===")
print(f"R2 Score     : {r2:.4f}  (1.0 = parfait)")
print(f"MAE          : {mae:.4f}  (erreur moyenne en points de %)")
print(f"Correlation  : {corr:.4f} (1.0 = parfait)")
print()

# Cross-validation R2 
print("Cross-validation 5 folds (R2)...")
cv_scores = cross_val_score(model, X, y, cv=5, scoring="r2", n_jobs=-1)
print(f"R2 CV : {cv_scores.mean():.4f} +/- {cv_scores.std():.4f}")
print(f"Scores: {[round(s,4) for s in cv_scores]}\n")

# Importance des features 
print("=== Importance des features ===")
for feat, imp in sorted(zip(FEATURES, model.feature_importances_), key=lambda x: -x[1]):
    bar = "|" * int(imp * 60)
    print(f"  {feat:<15} {imp:.4f}  {bar}")
print()

# Meilleurs creneaux par segment 
print("=== Meilleurs creneaux predits par segment ===")
JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

for seg in le_segment.classes_:
    seg_enc = le_segment.transform([seg])[0]
    resultats = []
    for secteur in le_secteur.classes_:
        sec_enc = le_secteur.transform([secteur])[0]
        for h in range(6, 22):
            for d in range(0, 7):
                score = model.predict([[h, d, seg_enc, sec_enc]])[0]
                resultats.append((score, h, d, secteur))

    resultats.sort(reverse=True)
    top = resultats[0]
    print(f"  {seg:<22} -> {JOURS[top[2]]} {top[1]:02d}h00  score={top[0]:.3f}  [{top[3]}]")

print()

# Sauvegarde 
models_dir = os.path.join(os.path.dirname(__file__), "..", "app", "models")
os.makedirs(models_dir, exist_ok=True)

joblib.dump(model,      os.path.join(models_dir, "timing_model.pkl"))
joblib.dump(le_segment, os.path.join(models_dir, "timing_le_segment.pkl"))
joblib.dump(le_secteur, os.path.join(models_dir, "timing_le_secteur.pkl"))

print(f"Modeles sauvegardes dans : {models_dir}")
print("  timing_model.pkl")
print("  timing_le_segment.pkl")
print("  timing_le_secteur.pkl")
print("\nPhase 2 terminee avec succes.")
