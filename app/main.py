import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

from .config import DEBUG, STATIC_DIR
from .database import get_db, init_db
from .models import (
    ModuleProgress, Participant, ParticipantState, ResultScore, SelfAssessment, utcnow,
)
from .schemas import AdminLoginIn, ProfileIn, RegisterIn, StateIn, SummaryIn
from .security import (
    check_admin_password, current_participant, hash_token, make_admin_token,
    new_token, rate_limit, require_admin,
)

MAX_STATE_BYTES = 200_000


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Ruta de IA para desarrolladores",
    lifespan=lifespan,
    docs_url="/docs" if DEBUG else None,
    redoc_url=None,
    openapi_url="/openapi.json" if DEBUG else None,
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


# ------------------------------------------------------------------ helpers
def to_ms(dt: datetime | None) -> int:
    return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000) if dt else 0


def profile_dict(p: Participant) -> dict:
    return {
        "id": p.public_id,
        "fullName": p.full_name,
        "area": p.area,
        "cargo": p.cargo,
        "nivel": p.nivel,
        "registeredAt": to_ms(p.registered_at),
    }


def admin_dict(p: Participant) -> dict:
    s = p.scores
    return {
        **profile_dict(p),
        "lastActivity": to_ms(p.last_activity),
        "step": p.current_step,
        "done": [m.step_id for m in sorted(p.modules, key=lambda m: m.completed_at)],
        "pre": {str(a.skill_index): a.score for a in p.assessments if a.phase == "pre"},
        "post": {str(a.skill_index): a.score for a in p.assessments if a.phase == "post"},
        "scores": {
            "mythsC": s.myths_correct if s else 0,
            "mythsT": s.myths_total if s else 0,
            "privC": s.priv_correct if s else 0,
            "privT": s.priv_total if s else 0,
            "quizC": s.quiz_correct if s else 0,
            "quizT": s.quiz_total if s else 0,
            "rub": s.rubric_done if s else 0,
        },
    }


def apply_summary(db: Session, p: Participant, sm: SummaryIn) -> None:
    """Sincroniza las tablas de progreso con el resumen enviado por la persona."""
    now = utcnow()
    p.current_step = sm.step
    p.last_activity = now

    keep = set(sm.done)
    for m in list(p.modules):
        if m.step_id not in keep:
            p.modules.remove(m)
    have = {m.step_id for m in p.modules}
    for step_id in sm.done:
        if step_id not in have:
            p.modules.append(ModuleProgress(step_id=step_id, completed_at=now))

    wanted = {(int(k), "pre"): v for k, v in sm.pre.items()}
    wanted.update({(int(k), "post"): v for k, v in sm.post.items()})
    existing = {(a.skill_index, a.phase): a for a in p.assessments}
    for key, a in existing.items():
        if key not in wanted:
            p.assessments.remove(a)
        else:
            a.score = wanted[key]
    for (idx, phase), score in wanted.items():
        if (idx, phase) not in existing:
            p.assessments.append(SelfAssessment(skill_index=idx, phase=phase, score=score))

    sc = sm.scores
    if p.scores is None:
        p.scores = ResultScore()
    p.scores.myths_correct, p.scores.myths_total = sc.mythsC, sc.mythsT
    p.scores.priv_correct, p.scores.priv_total = sc.privC, sc.privT
    p.scores.quiz_correct, p.scores.quiz_total = sc.quizC, sc.quizT
    p.scores.rubric_done = sc.rub


def load_with_children(db: Session, p: Participant) -> Participant:
    return db.scalar(
        select(Participant)
        .where(Participant.id == p.id)
        .options(
            selectinload(Participant.modules),
            selectinload(Participant.assessments),
            selectinload(Participant.scores),
            selectinload(Participant.state),
        )
    )


# --------------------------------------------------------------- participante
@app.post("/api/register", status_code=201)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    rate_limit(request, "register", limit=30, window_s=3600)
    token = new_token()
    p = Participant(
        token_hash=hash_token(token),
        full_name=body.fullName,
        area=body.area,
        cargo=body.cargo,
        nivel=body.nivel,
        consent=True,
    )
    db.add(p)
    db.commit()
    return {"token": token, "participant": profile_dict(p)}


@app.get("/api/me")
def me(p: Participant = Depends(current_participant), db: Session = Depends(get_db)):
    p = load_with_children(db, p)
    state = json.loads(p.state.state_json) if p.state else None
    return {**profile_dict(p), "state": state}


@app.put("/api/me")
def update_profile(
    body: ProfileIn, p: Participant = Depends(current_participant), db: Session = Depends(get_db)
):
    p.full_name, p.area, p.cargo, p.nivel = body.fullName, body.area, body.cargo, body.nivel
    p.last_activity = utcnow()
    db.commit()
    return profile_dict(p)


@app.put("/api/state", status_code=204)
def save_state(
    body: StateIn, p: Participant = Depends(current_participant), db: Session = Depends(get_db)
):
    raw = json.dumps(body.state, ensure_ascii=False, separators=(",", ":"))
    if len(raw.encode()) > MAX_STATE_BYTES:
        raise HTTPException(413, "El estado es demasiado grande")
    p = load_with_children(db, p)
    apply_summary(db, p, body.summary)
    if p.state is None:
        p.state = ParticipantState(state_json=raw)
    else:
        p.state.state_json = raw
        p.state.updated_at = utcnow()
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------------- admin
@app.post("/api/admin/login")
def admin_login(body: AdminLoginIn, request: Request):
    rate_limit(request, "admin_login", limit=8, window_s=600)
    if not check_admin_password(body.password):
        raise HTTPException(401, "Contraseña incorrecta")
    return {"token": make_admin_token()}


@app.get("/api/admin/me", dependencies=[Depends(require_admin)])
def admin_me():
    return {"ok": True}


@app.get("/api/admin/participants", dependencies=[Depends(require_admin)])
def admin_participants(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Participant)
        .options(
            selectinload(Participant.modules),
            selectinload(Participant.assessments),
            selectinload(Participant.scores),
        )
        .order_by(Participant.last_activity.desc())
    ).all()
    return [admin_dict(p) for p in rows]


@app.delete("/api/admin/participants/{public_id}", status_code=204, dependencies=[Depends(require_admin)])
def admin_delete(public_id: str, db: Session = Depends(get_db)):
    p = db.scalar(select(Participant).where(Participant.public_id == public_id))
    if not p:
        raise HTTPException(404, "No existe")
    db.delete(p)
    db.commit()
    return Response(status_code=204)


# ------------------------------------------------------------ salud y frontend
@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(
        STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"}, media_type="text/html"
    )
