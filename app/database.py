import time

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL

_is_sqlite = DATABASE_URL.startswith("sqlite")
if _is_sqlite:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # Pool de conexiones para atender muchos usuarios a la vez sin lentitud
    engine = create_engine(
        DATABASE_URL, pool_size=10, max_overflow=20, pool_pre_ping=True, pool_recycle=1800
    )

if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Crea las tablas si no existen (seguro con varios workers arrancando a la vez)."""
    from . import models  # noqa: F401  (registra las tablas)

    for attempt in range(3):
        try:
            Base.metadata.create_all(bind=engine)
            return
        except Exception:  # carrera entre workers: reintenta
            if attempt == 2:
                raise
            time.sleep(1)
