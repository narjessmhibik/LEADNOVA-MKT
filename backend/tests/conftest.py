import os

# Doit être défini AVANT tout import de l'application
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_leadpilot.db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_pytest_only")
os.environ.setdefault("BREVO_API_KEY", "test_brevo_key")
os.environ.setdefault("OPENROUTER_API_KEY", "test_openrouter_key")
os.environ.setdefault("GROQ_API_KEY", "test_groq_key")

# Patch sqlalchemy.create_engine pour gérer sqlite+aiosqlite sur l'engine synchrone
import sqlalchemy as _sa
_orig_create_engine = _sa.create_engine

def _patched_create_engine(url, **kw):
    url_str = str(url)
    if "sqlite+aiosqlite" in url_str:
        url_str = url_str.replace("sqlite+aiosqlite", "sqlite")
    return _orig_create_engine(url_str, **kw)

_sa.create_engine = _patched_create_engine

import pytest
import pytest_asyncio

# Import app.main ICI (niveau module) pour enregistrer TOUS les modèles dans
# Base.metadata AVANT que db_session ne lance drop_all / create_all.
# Sans cet import, create_all tournait avec un Base vide → tables manquantes
# → les for-loops des endpoints ne s'exécutaient jamais → coverage faussé.
from app.main import app as _app  # noqa: F401 — effet de bord voulu
from app.database import Base, engine, SessionLocal


@pytest_asyncio.fixture
async def db_session():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def api_client(db_session):
    from app.main import app
    from app.database import get_db
    from httpx import AsyncClient, ASGITransport

    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
