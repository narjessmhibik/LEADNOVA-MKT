from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean
from app.database import Base
from datetime import datetime

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    email = Column(String, index=True, nullable=True)
    company = Column(String, nullable=True)
    job_title = Column(String, nullable=True)
    phone = Column(String, nullable=True)

    # Champs scraping
    address = Column(String, nullable=True)
    website = Column(String, nullable=True)
    sector = Column(String, nullable=True)
    region = Column(String, nullable=True)
    reviews_count = Column(Integer, nullable=True)
    reviews_average = Column(Float, nullable=True)
    scraping_url = Column(String, nullable=True)
    score_fiabilite = Column(Float, default=0.0)

    # Champs enrichissement IA (nouveaux)
    description = Column(Text, nullable=True)        # Description générée par IA
    company_type = Column(String, nullable=True)     # PME / Startup / Grande entreprise
    email_confidence = Column(Float, nullable=True)  # Score confiance Hunter.io (0-100)
    email_pattern = Column(String, nullable=True)    # Pattern email trouvé
    services = Column(String, nullable=True)         # Services proposés (JSON string)
    enriched = Column(Boolean, default=False)        # Lead enrichi ou non
    enriched_at = Column(DateTime, nullable=True)    # Date enrichissement

    source = Column(String, default="manual")
    score = Column(Float, default=0.0)
    status = Column(String, default="new")
    created_at = Column(DateTime, default=datetime.utcnow)
    scraped_at = Column(DateTime, nullable=True)   # date de scraping (fraîcheur)

    # Scoring XGBoost + Segmentation K-Means
    lead_score = Column(Float, nullable=True)
    scored_at = Column(DateTime, nullable=True)
    segment = Column(String, nullable=True)
    segmented_at = Column(DateTime, nullable=True)

    # Email Generator
    email_subject_a = Column(String, nullable=True)
    email_body_a = Column(Text, nullable=True)
    email_subject_b = Column(String, nullable=True)
    email_body_b = Column(Text, nullable=True)
    email_sent = Column(Boolean, default=False)
    email_sent_at = Column(DateTime, nullable=True)
    ab_version = Column(String(1), nullable=True)   # 'A' ou 'B'
    email_opened = Column(Boolean, default=False)
    email_opened_at = Column(DateTime, nullable=True)
    email_clicked = Column(Boolean, default=False)
    email_clicked_at = Column(DateTime, nullable=True)
    followup_sent = Column(Boolean, default=False)     # relance J+3 envoyée
    followup_sent_at = Column(DateTime, nullable=True)

    # SMS Twilio
    sms_sent = Column(Boolean, default=False)
    sms_sent_at = Column(DateTime, nullable=True)
    sms_body = Column(Text, nullable=True)
    sms_status = Column(String, nullable=True)  # delivered / failed / queued