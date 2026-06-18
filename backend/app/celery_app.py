from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    "leadpilot",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
    include=["app.tasks"],
)

celery_app.conf.beat_schedule = {
    # Sélection automatique du gagnant A/B — toutes les heures
    "select-ab-winner-hourly": {
        "task": "app.tasks.select_ab_winner",
        "schedule": crontab(minute=0),  # à HH:00 chaque heure
    },
    # Relance email J+3 — chaque matin à 9h
    "followup-emails-daily": {
        "task": "app.tasks.send_followup_emails",
        "schedule": crontab(hour=9, minute=0),
    },
}