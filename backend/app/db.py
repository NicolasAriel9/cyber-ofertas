import re

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# Supabase's session pooler (port 5432) refuses clients beyond its pool size
# (15 on the free plan), less than the scraper's parallel jobs plus the API.
# Its transaction pooler (6543) shares those connections between clients.
SUPABASE_SESSION_POOLER = re.compile(r"(@[^/@]+\.pooler\.supabase\.com):5432(?=/|$)")


def normalize_database_url(url: str) -> str:
    """Neon/Render hand out postgres:// or postgresql:// URLs, which SQLAlchemy
    maps to psycopg2; this project installs psycopg 3."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+psycopg://" + url[len(prefix):]
            break
    return SUPABASE_SESSION_POOLER.sub(r"\1:6543", url)


def engine_connect_args(url: str, connect_timeout: int = 15) -> dict:
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    # A transaction pooler hands each transaction a different server
    # connection, where psycopg's prepared statements wouldn't exist. A busy
    # pooler can leave a connection attempt hanging: give up and retry later.
    return {"prepare_threshold": None, "connect_timeout": connect_timeout}


def engine_pool_args(url: str) -> dict:
    if url.startswith("sqlite"):
        return {}
    # The free database shares ~15 server connections between the API and
    # 15 parallel scrape jobs; SQLAlchemy's default (up to 15 per process)
    # let the API alone take them all.
    return {"pool_size": 3, "max_overflow": 2, "pool_timeout": 30}


database_url = normalize_database_url(settings.database_url)
engine = create_engine(
    database_url,
    connect_args=engine_connect_args(database_url),
    pool_pre_ping=True,
    **engine_pool_args(database_url),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
