from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from app.database import Base
from datetime import datetime

class ScrapingJob(Base):
    __tablename__ = "scraping_jobs"

    id              = Column(Integer, primary_key=True, index=True)
    name            = Column(String, nullable=False)
    source          = Column(String, nullable=False)        # LinkedIn, Google Maps, Pages Jaunes...
    keywords        = Column(String, nullable=True)
    location        = Column(String, nullable=True)
    sector          = Column(String, nullable=True)
    max_leads       = Column(Integer, default=100)
    leads_collected = Column(Integer, default=0)
    status          = Column(String, default="en_attente")  # en_attente / actif / termine / erreur
    success_rate    = Column(Float, default=0.0)
    error_message   = Column(String, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    started_at      = Column(DateTime, nullable=True)
    finished_at     = Column(DateTime, nullable=True)
