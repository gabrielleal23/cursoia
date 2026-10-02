import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Falta la variable de entorno {name}. Revisa tu archivo .env")
    return value


SECRET_KEY = _required("SECRET_KEY")
ADMIN_PASSWORD = _required("ADMIN_PASSWORD")
ADMIN_TOKEN_HOURS = int(os.environ.get("ADMIN_TOKEN_HOURS", "12"))
DEBUG = os.environ.get("DEBUG", "0") == "1"



def _normalize_db_url(url: str) -> str:
    """Railway entrega postgresql://...; SQLAlchemy necesita el driver psycopg (v3)."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


# En Railway: DATABASE_URL viene de PostgreSQL. En local: SQLite automático.
_db = os.environ.get("DATABASE_URL", "").strip()
if not _db:
    (BASE_DIR / "data").mkdir(exist_ok=True)
    _db = f"sqlite:///{BASE_DIR / 'data' / 'ruta_ia.db'}"
DATABASE_URL = _normalize_db_url(_db)
STATIC_DIR = BASE_DIR / "static"
