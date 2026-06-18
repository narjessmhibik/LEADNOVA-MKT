from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from app.database import get_db, SyncSessionLocal
from app.models.notification import Notification
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


def push_notification(type: str, title: str, message: str = None):
    db = SyncSessionLocal()
    try:
        n = Notification(type=type, title=title, message=message)
        db.add(n)
        db.commit()
    except Exception as e:
        logger.error(f"[NOTIF] Erreur push_notification: {e}")
        db.rollback()
    finally:
        db.close()


async def push_notification_async(db: AsyncSession, type: str, title: str, message: str = None):
    db.add(Notification(type=type, title=title, message=message))
    await db.commit()


@router.get("/")
async def list_notifications(limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Notification).order_by(Notification.created_at.desc()).limit(limit)
    )
    items = result.scalars().all()

    unread = await db.execute(
        select(func.count(Notification.id)).where(Notification.is_read == False)
    )
    unread_count = unread.scalar() or 0

    return {
        "unread": unread_count,
        "items": [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "message": n.message,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in items
        ],
    }


@router.post("/{notif_id}/read")
async def mark_read(notif_id: int, db: AsyncSession = Depends(get_db)):
    await db.execute(
        update(Notification).where(Notification.id == notif_id).values(is_read=True)
    )
    await db.commit()
    return {"status": "ok"}


@router.post("/read-all")
async def mark_all_read(db: AsyncSession = Depends(get_db)):
    await db.execute(update(Notification).values(is_read=True))
    await db.commit()
    return {"status": "ok"}


@router.delete("/")
async def clear_all(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import delete
    await db.execute(delete(Notification))
    await db.commit()
    return {"status": "ok"}
