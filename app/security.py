import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import ADMIN_PASSWORD, ADMIN_TOKEN_HOURS, SECRET_KEY
from .database import get_db
from .models import Participant


# ---------- tokens de participante (aleatorios, se guarda solo su hash) ----------
def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---------- token de administrador (firmado, con vencimiento) ----------
def _sign(payload: str) -> str:
    return hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()


def check_admin_password(password: str) -> bool:
    return hmac.compare_digest(password.encode(), ADMIN_PASSWORD.encode())


def make_admin_token() -> str:
    payload = f"admin.{int(time.time()) + ADMIN_TOKEN_HOURS * 3600}"
    return f"{payload}.{_sign(payload)}"


def _valid_admin_token(token: str) -> bool:
    try:
        role, exp, sig = token.split(".")
        return (
            role == "admin"
            and int(exp) > time.time()
            and hmac.compare_digest(sig, _sign(f"{role}.{exp}"))
        )
    except ValueError:
        return False


# ---------- dependencias de FastAPI ----------
def _bearer(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, "No autenticado")
    return auth[7:].strip()


def current_participant(request: Request, db: Session = Depends(get_db)) -> Participant:
    token = _bearer(request)
    p = db.scalar(select(Participant).where(Participant.token_hash == hash_token(token)))
    if not p:
        raise HTTPException(401, "Código inválido")
    return p


def require_admin(request: Request) -> None:
    if not _valid_admin_token(_bearer(request)):
        raise HTTPException(401, "Sesión de administrador inválida o vencida")


# ---------- límite de intentos (en memoria, por proceso) ----------
_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(request: Request, bucket: str, limit: int, window_s: int) -> None:
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?")
    q = _hits[f"{bucket}:{ip}"]
    now = time.time()
    while q and q[0] < now - window_s:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(429, "Demasiados intentos. Espera unos minutos.")
    q.append(now)
