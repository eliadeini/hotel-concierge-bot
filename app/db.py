import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    kwargs = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        # In-memory SQLite must share a single connection or tables vanish
        # between sessions (used by the test suite).
        if url == "sqlite://" or ":memory:" in url:
            kwargs["poolclass"] = StaticPool
    return create_engine(url, **kwargs)


engine = _make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    import app.models  # noqa: F401 — registers tables on Base.metadata

    if settings.database_url.startswith("sqlite:///"):
        path = settings.database_url.removeprefix("sqlite:///")
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
