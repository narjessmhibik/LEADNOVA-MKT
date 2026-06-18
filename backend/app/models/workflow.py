from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base
from datetime import datetime

class Workflow(Base):
    __tablename__ = "workflows"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String, nullable=False)
    trigger     = Column(String, default="manual")
    status      = Column(String, default="active")  # active | paused
    description = Column(String, nullable=True)
    actions     = Column(String, default="email")   # comma-separated
    executions  = Column(Integer, default=0)
    emails_sent = Column(Integer, default=0)
    created_at  = Column(DateTime, default=datetime.utcnow)
