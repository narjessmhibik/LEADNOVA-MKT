from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from app.database import Base
from datetime import datetime

class Opportunity(Base):
    __tablename__ = "opportunities"

    id          = Column(Integer, primary_key=True, index=True)
    title       = Column(String, nullable=False)
    company     = Column(String, nullable=True)
    lead_id     = Column(Integer, ForeignKey("leads.id"), nullable=True)
    value       = Column(Float, default=0.0)
    stage       = Column(String, default="Prospection")
    probability = Column(Float, default=30.0)
    risk        = Column(Boolean, default=False)
    notes       = Column(String, nullable=True)
    expected_close = Column(DateTime, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)