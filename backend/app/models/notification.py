from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.database import Base
from datetime import datetime

class Notification(Base):
    __tablename__ = "notifications"

    id         = Column(Integer, primary_key=True, index=True)
    type       = Column(String, default="info")
    title      = Column(String, nullable=False)
    message    = Column(String, nullable=True)
    is_read    = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
