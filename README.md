# LeadPilot

**Plateforme unifiée de Marketing & Sales Automation avec scraping de leads et IA.**

LeadPilot couvre l'intégralité du cycle de vie d'un lead :
**Découverte (scraping) -> Enrichissement (IA) -> Nurturing (campagnes) -> Conversion (sales forecasting).**

---

## Fonctionnalités principales

- **Scraping multi-sources** : Google Maps, Pages Jaunes, LinkedIn
- **Enrichissement IA** : email finder (Hunter.io + pattern matching), score de fiabilité
- **Lead Scoring** : modèle XGBoost (score 0-100)
- **Segmentation** : K-Means (Chaud, Froid, À Risque, Prêts à Acheter)
- **Campagnes email** : génération de contenu par IA (OpenRouter)
- **A/B Testing** : sélection automatique du gagnant après 24h (Celery)
- **ML Timing** : meilleur horaire d'envoi par segment (Random Forest)
- **Tracking** : ouverture (pixel) et clics (lien tracké)
- **Workflows d'automation** : séquences déclenchées par événement
- **Pipeline Sales** : Kanban des opportunités (drag & drop)
- **Notifications temps réel** : cloche avec polling
- **Exports** : Excel (pandas) et PDF (reportlab + html2canvas)
- **Dashboard unifié** : KPIs Scraping + Marketing + Sales, Funnel, Alertes IA

---

## Stack technique

| Couche | Technologies |
|---|---|
| **Backend** | FastAPI · SQLAlchemy (async) · Pydantic |
| **Base de données** | PostgreSQL 15 |
| **Tâches async** | Celery · Celery Beat · Redis |
| **Machine Learning** | XGBoost · scikit-learn (K-Means, Random Forest) |
| **Scraping** | Playwright · BeautifulSoup |
| **Frontend** | React 18 · TypeScript · Vite · Tailwind · Recharts |
| **IA générative** | OpenRouter - Groq |
| **Emails** | Brevo |

---

## Prérequis

- **Python 3.11+**
- **Node.js 18+**
- **PostgreSQL 15** et **Redis** (ou via Docker — voir plus bas)

---

## Installation

### 1. Cloner le projet
```bash
git clone <url-du-repo>
cd leadpilot
```

### 2. Configurer les variables d'environnement
```bash
# Copier le modèle et remplir avec vos clés
cp .env.example .env
cp .env.example backend/.env
```
Éditer `.env` et renseigner au minimum : `DATABASE_URL`, `SECRET_KEY`, `REDIS_URL`.
Les clés API (Hunter, OpenRouter, Brevo) sont nécessaires pour l'enrichissement et les emails.

### 3. Lancer PostgreSQL + Redis (via Docker)
```bash
docker-compose up -d
```

### 4. Restaurer les données de démonstration
Un dump SQL (`backend/seed/leadpilot.sql`) contient un jeu de données complet
(leads, campagnes, opportunités...). À importer une fois la base lancée :

```bash
# Via Docker (conteneur nommé leadpilot-db-1)
docker exec -i leadpilot-db-1 psql -U leadpilot -d leadpilot_db < backend/seed/leadpilot.sql

# Ou avec psql en local
psql -U leadpilot -d leadpilot_db -f backend/seed/leadpilot.sql
```

### 5. Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
playwright install chromium    # navigateur pour le scraping

# Lancer l'API
uvicorn app.main:app --reload
```
API disponible sur **http://127.0.0.1:8000** · Documentation Swagger : **/docs**

### 6. Worker Celery (tâches de fond : scraping, A/B, emails)
Dans un terminal séparé (venv activé) :
```bash
cd backend
celery -A app.celery_app worker --loglevel=info --pool=solo   # --pool=solo requis sur Windows
celery -A app.celery_app beat   --loglevel=info               # tâches planifiées (autre terminal)
```

### 7. Frontend
```bash
cd frontend
npm install
npm run dev
```
Application disponible sur **http://localhost:5173**

> URL du backend : le frontend cible `http://127.0.0.1:8000` par défaut.
> Pour la changer (ex: accès réseau), créer `frontend/.env` :
> ```
> VITE_API_URL=http://127.0.0.1:8000
> ```

---

## Modèles Machine Learning

Les modèles entraînés (`.pkl`) ne sont **pas versionnés** (trop volumineux pour git).
Une fois les données restaurées (étape 4), les régénérer ainsi :

```bash
cd backend

# Lead scoring (XGBoost) + segmentation (K-Means) — nécessite les données
python train_model.py

# ML Timing (Random Forest) — données simulées, aucune donnée requise
python scripts/generate_timing_data.py
python scripts/train_timing_model.py

# Probabilité de closing des deals (XGBoost) — données simulées
python scripts/train_closing_model.py
```

> Important : `train_model.py` s'appuie sur les leads en base. Restaurer le dump
> (étape 4) **avant** de lancer l'entraînement, sinon il n'y a pas de données.

Les modèles ML (scoring, timing, closing) se réentraînent automatiquement sur les
données réelles dès qu'un seuil est atteint (via Celery).

---

## Structure du projet

```
leadpilot/
├── backend/
│   ├── app/
│   │   ├── routers/        # Endpoints API (auth, leads, campaigns, ...)
│   │   ├── models/         # Modèles SQLAlchemy
│   │   ├── linkedin_scraper/
│   │   ├── scraper.py      # Scraper principal (Maps, Pages Jaunes)
│   │   ├── enrichment.py   # Enrichissement IA des leads
│   │   ├── tasks.py        # Tâches Celery
│   │   ├── email_generator.py
│   │   └── main.py         # Point d'entrée FastAPI
│   ├── scripts/            # Génération/entraînement modèles ML
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── pages/          # Dashboard, Leads, Campaigns, Ventes, ...
│       └── components/     # Navbar, NotificationBell, ...
├── docker-compose.yml      # PostgreSQL + Redis
└── .env.example
```

---

## Premier démarrage

1. Créer un compte via `POST /auth/register` (ou la page de connexion du frontend)
2. Se connecter pour obtenir un token JWT
3. Lancer un job de scraping depuis la page **Scraping**
4. Les leads sont enrichis, scorés et segmentés automatiquement
5. Créer une campagne email depuis la page **Campagnes**
