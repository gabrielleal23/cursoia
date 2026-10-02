from typing import Any

from pydantic import BaseModel, Field, field_validator

STEP_IDS = ("inicio", "m1", "m2", "m3", "m4", "m5", "cierre")


class ProfileIn(BaseModel):
    fullName: str = Field(min_length=1, max_length=80)
    area: str = Field(min_length=1, max_length=80)
    cargo: str = Field(min_length=1, max_length=40)
    nivel: str = Field(min_length=1, max_length=20)

    @field_validator("fullName", "area", "cargo", "nivel")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Campo vacío")
        return v


class RegisterIn(ProfileIn):
    consent: bool

    @field_validator("consent")
    @classmethod
    def _must_consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Debes aceptar el consentimiento")
        return v


class Scores(BaseModel):
    mythsC: int = Field(0, ge=0, le=100)
    mythsT: int = Field(0, ge=0, le=100)
    privC: int = Field(0, ge=0, le=100)
    privT: int = Field(0, ge=0, le=100)
    quizC: int = Field(0, ge=0, le=100)
    quizT: int = Field(0, ge=0, le=100)
    rub: int = Field(0, ge=0, le=100)


class SummaryIn(BaseModel):
    step: int = Field(0, ge=0, le=len(STEP_IDS) - 1)
    done: list[str] = []
    pre: dict[str, int] = {}
    post: dict[str, int] = {}
    scores: Scores = Scores()

    @field_validator("done")
    @classmethod
    def _done(cls, v: list[str]) -> list[str]:
        if any(x not in STEP_IDS for x in v):
            raise ValueError("Módulo desconocido")
        return list(dict.fromkeys(v))

    @field_validator("pre", "post")
    @classmethod
    def _ratings(cls, v: dict[str, int]) -> dict[str, int]:
        for k, n in v.items():
            if k not in {"0", "1", "2", "3", "4"} or not 1 <= n <= 5:
                raise ValueError("Autoevaluación inválida")
        return v


class StateIn(BaseModel):
    state: dict[str, Any]
    summary: SummaryIn


class AdminLoginIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)
