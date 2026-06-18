from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import leads, auth, campaigns, opportunities, scraping, workflows, notifications
from app.database import engine, Base
from contextlib import asynccontextmanager

# Import tous les modèles pour que create_all les détecte
from app.models import lead, campaign, opportunity, scraping_job, workflow, notification  # noqa

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="LeadPilot API", version="1.0", lifespan=lifespan)

# CORS pour permettre au frontend de communiquer avec le backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(leads.router, prefix="/leads", tags=["Leads"])
app.include_router(campaigns.router, prefix="/campaigns", tags=["Campaigns"])
app.include_router(opportunities.router, prefix="/opportunities", tags=["Opportunities"])
app.include_router(scraping.router, prefix="/scraping", tags=["Scraping"])
app.include_router(workflows.router, prefix="/workflows", tags=["Workflows"])
app.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])

@app.get("/")
def root():
    return {"message": "LeadPilot API is running "}