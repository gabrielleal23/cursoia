import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Participant(Base):
    """Persona registrada en la capacitación."""

    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, default=lambda: uuid.uuid4().hex
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(80))
    area: Mapped[str] = mapped_column(String(80), index=True)
    cargo: Mapped[str] = mapped_column(String(40))
    nivel: Mapped[str] = mapped_column(String(20))
    consent: Mapped[bool] = mapped_column(Boolean, default=True)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    registered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_activity: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    modules: Mapped[list["ModuleProgress"]] = relationship(
        back_populates="participant", cascade="all, delete-orphan"
    )
    assessments: Mapped[list["SelfAssessment"]] = relationship(
        back_populates="participant", cascade="all, delete-orphan"
    )
    scores: Mapped["ResultScore | None"] = relationship(
        back_populates="participant", cascade="all, delete-orphan", uselist=False
    )
    state: Mapped["ParticipantState | None"] = relationship(
        back_populates="participant", cascade="all, delete-orphan", uselist=False
    )


class ModuleProgress(Base):
    """Módulos completados por participante."""

    __tablename__ = "module_progress"

    participant_id: Mapped[int] = mapped_column(
        ForeignKey("participants.id", ondelete="CASCADE"), primary_key=True
    )
    step_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    participant: Mapped[Participant] = relationship(back_populates="modules")


class SelfAssessment(Base):
    """Autoevaluación de habilidades (1 a 5), antes ('pre') y después ('post')."""

    __tablename__ = "self_assessments"
    __table_args__ = (
        CheckConstraint("score BETWEEN 1 AND 5", name="ck_score_range"),
        CheckConstraint("phase IN ('pre','post')", name="ck_phase"),
        CheckConstraint("skill_index BETWEEN 0 AND 4", name="ck_skill_index"),
    )

    participant_id: Mapped[int] = mapped_column(
        ForeignKey("participants.id", ondelete="CASCADE"), primary_key=True
    )
    skill_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    phase: Mapped[str] = mapped_column(String(4), primary_key=True)
    score: Mapped[int] = mapped_column(Integer)

    participant: Mapped[Participant] = relationship(back_populates="assessments")


class ResultScore(Base):
    """Resultados resumidos de los ejercicios (visibles para el admin)."""

    __tablename__ = "result_scores"

    participant_id: Mapped[int] = mapped_column(
        ForeignKey("participants.id", ondelete="CASCADE"), primary_key=True
    )
    myths_correct: Mapped[int] = mapped_column(Integer, default=0)
    myths_total: Mapped[int] = mapped_column(Integer, default=0)
    priv_correct: Mapped[int] = mapped_column(Integer, default=0)
    priv_total: Mapped[int] = mapped_column(Integer, default=0)
    quiz_correct: Mapped[int] = mapped_column(Integer, default=0)
    quiz_total: Mapped[int] = mapped_column(Integer, default=0)
    rubric_done: Mapped[int] = mapped_column(Integer, default=0)

    participant: Mapped[Participant] = relationship(back_populates="scores")


class ParticipantState(Base):
    """Estado completo y PRIVADO de cada persona (prompts, notas, plan). No se expone al admin."""

    __tablename__ = "participant_state"

    participant_id: Mapped[int] = mapped_column(
        ForeignKey("participants.id", ondelete="CASCADE"), primary_key=True
    )
    state_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    participant: Mapped[Participant] = relationship(back_populates="state")


Index("ix_module_progress_step", ModuleProgress.step_id)
