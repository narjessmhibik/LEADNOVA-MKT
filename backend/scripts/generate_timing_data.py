import numpy as np
import pandas as pd
import os

np.random.seed(42)
N = 50_000

SEGMENTS = ["Chaud", "Prêts à Acheter", "Froid", "À Risque"]
SECTEURS = [
    "Informatique & Tech",
    "Services aux entreprises",
    "Marketing & Communication",
    "Santé",
    "Education & Formation",
    "Industrie & Production",
    "Construction & BTP",
    "Immobilier",
    "Finance & Comptabilité",
    "Juridique",
    "Sécurité",
    "Management & Conseil",
    "Architecture & Urbanisme",
    "Commerce & Distribution",
    "Agriculture & Alimentaire",
    "Energie & Environnement",
    "Tourisme & Loisirs",
    "Tourisme & Voyages",
    "Mode & Accessoires",
    "Restauration & Hôtellerie",
    "Culture & Musées",
    "Culture & Patrimoine",
]

# Taux d'ouverture de base par segment 
SEGMENT_BASE_RATE = {
    "Chaud":             0.45,
    "Prêts à Acheter":   0.35,
    "Froid":             0.20,
    "À Risque":          0.12,
}

# Bonus par heure générique (commun à tous les segments)
def hour_bonus(h):
    matin  = np.exp(-0.5 * ((h - 9.5) / 1.5) ** 2) * 0.25
    aprem  = np.exp(-0.5 * ((h - 14.5) / 1.5) ** 2) * 0.20
    return float(matin + aprem)

# Pic horaire préféré par segment (différencie l'heure optimale par profil CRM)
HOUR_PEAK_BY_SEGMENT = {
    "Chaud":           {"peak": 9,  "bonus": 0.12},  # décideurs actifs tôt le matin
    "Prêts à Acheter": {"peak": 11, "bonus": 0.10},  # phase de recherche en milieu de matinée
    "Froid":           {"peak": 14, "bonus": 0.09},  # plus réceptifs l'après-midi
    "À Risque":        {"peak": 16, "bonus": 0.08},  # fin de journée pour les profils difficiles
}

# Bonus par jour PAR SEGMENT (0=lundi ... 6=dimanche) 
DAY_BONUS_BY_SEGMENT = {
    "Chaud": {
        0: 0.05, 1: 0.18, 2: 0.10, 3: 0.15, 4: 0.03, 5: -0.10, 6: -0.12,
    },
    "Prêts à Acheter": {
        0: 0.06, 1: 0.10, 2: 0.15, 3: 0.14, 4: 0.05, 5: -0.09, 6: -0.11,
    },
    "Froid": {
        0: 0.14, 1: 0.08, 2: 0.13, 3: 0.06, 4: 0.02, 5: -0.10, 6: -0.12,
    },
    "À Risque": {
        0: 0.04, 1: 0.07, 2: 0.08, 3: 0.10, 4: 0.14, 5: -0.08, 6: -0.11,
    },
}

# Heure préférée par secteur (décalage sur la courbe)
SECTOR_HOUR_PREF = {
    "Informatique & Tech":        {"peak": 10, "bonus": 0.08},
    "Services aux entreprises":   {"peak": 9,  "bonus": 0.06},
    "Marketing & Communication":  {"peak": 14, "bonus": 0.07},
    "Santé":                      {"peak": 12, "bonus": 0.07},
    "Education & Formation":      {"peak": 10, "bonus": 0.05},
    "Industrie & Production":     {"peak": 8,  "bonus": 0.05},
    "Construction & BTP":         {"peak": 8,  "bonus": 0.04},
    "Immobilier":                 {"peak": 11, "bonus": 0.05},
    "Finance & Comptabilité":     {"peak": 9,  "bonus": 0.06},
    "Juridique":                  {"peak": 10, "bonus": 0.05},
    "Sécurité":                   {"peak": 9,  "bonus": 0.04},
    "Management & Conseil":       {"peak": 10, "bonus": 0.06},
    "Architecture & Urbanisme":   {"peak": 9,  "bonus": 0.05},
    "Commerce & Distribution":    {"peak": 10, "bonus": 0.06},
    "Agriculture & Alimentaire":  {"peak": 8,  "bonus": 0.05},
    "Energie & Environnement":    {"peak": 10, "bonus": 0.05},
    "Tourisme & Loisirs":         {"peak": 14, "bonus": 0.06},
    "Tourisme & Voyages":         {"peak": 14, "bonus": 0.06},
    "Mode & Accessoires":         {"peak": 14, "bonus": 0.07},
    "Restauration & Hôtellerie":  {"peak": 10, "bonus": 0.05},
    "Culture & Musées":           {"peak": 11, "bonus": 0.04},
    "Culture & Patrimoine":       {"peak": 11, "bonus": 0.04},
}

# Génération 
rows = []
for _ in range(N):
    segment = np.random.choice(SEGMENTS)
    secteur = np.random.choice(SECTEURS)
    heure   = np.random.randint(0, 24)
    jour    = np.random.randint(0, 7)
    p = SEGMENT_BASE_RATE[segment]

    p += hour_bonus(heure)

    # Bonus horaire spécifique au segment
    seg_peak = HOUR_PEAK_BY_SEGMENT[segment]
    p += np.exp(-0.5 * ((heure - seg_peak["peak"]) / 2) ** 2) * seg_peak["bonus"]

    p += DAY_BONUS_BY_SEGMENT[segment][jour]

    pref = SECTOR_HOUR_PREF[secteur]
    p += np.exp(-0.5 * ((heure - pref["peak"]) / 2) ** 2) * pref["bonus"]

    p += np.random.normal(0, 0.03)

    p = float(np.clip(p, 0.0, 1.0))

    ouvert = int(np.random.binomial(1, p))

    rows.append({
        "heure":   heure,
        "jour":    jour,
        "segment": segment,
        "secteur": secteur,
        "p_theo":  round(p, 4),   # probabilité théorique (pour debug)
        "ouvert":  ouvert,
    })

df = pd.DataFrame(rows)

# Stats de validation 
print("=== Stats générales ===")
print(f"Total lignes      : {len(df)}")
print(f"Taux ouverture    : {df['ouvert'].mean():.1%}")
print()

print("=== Taux par segment ===")
print(df.groupby("segment")["ouvert"].mean().round(3).to_string())
print()

print("=== Top 5 heures (taux ouverture) ===")
print(df.groupby("heure")["ouvert"].mean().sort_values(ascending=False).head(5).round(3).to_string())
print()

print("=== Taux par jour (0=lundi) ===")
print(df.groupby("jour")["ouvert"].mean().round(3).to_string())

# Sauvegarde 
out_dir = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "timing_data.csv")
df.to_csv(out_path, index=False)
print(f"\nFichier sauvegardé : {out_path}")
print(f"Taille             : {os.path.getsize(out_path) / 1024:.0f} KB")
