from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from app.database import Base
from datetime import datetime

class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    subject = Column(String)
    content = Column(Text)
    status = Column(String, default="draft")
    channel = Column(String, default="email")
    open_rate = Column(Float, default=0.0)
    click_rate = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Champs enrichis
    campaign_name   = Column(String, nullable=True)
    leads_targeted  = Column(Integer, default=0)
    leads_sent      = Column(Integer, default=0)
    campaign_status = Column(String, default="draft")
    scheduled_at    = Column(DateTime, nullable=True)
    completed_at    = Column(DateTime, nullable=True)
    segment_filter  = Column(String, nullable=True)
    sector_filter   = Column(String, nullable=True)
    region_filter   = Column(String, nullable=True)
    tone            = Column(String, nullable=True)
    cta             = Column(String, nullable=True)
