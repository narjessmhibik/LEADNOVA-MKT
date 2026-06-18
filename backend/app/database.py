from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import os

load_dotenv()

# Fix Avast antivirus interference with asyncpg SSL keylog
os.environ.pop("SSLKEYLOGFILE", None)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://leadpilot:secret@localhost:5432/leadpilot_db"
)

# S'assurer que l'URL utilise asyncpg
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(DATABASE_URL, echo=True)

SessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with SessionLocal() as session:
        yield session

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker as sync_sessionmaker

# URL synchrone pour Celery (psycopg2 au lieu de asyncpg)
SYNC_DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

sync_engine = create_engine(SYNC_DATABASE_URL, echo=False)

SyncSessionLocal = sync_sessionmaker(
    autocommit=False, autoflush=False, bind=sync_engine
)