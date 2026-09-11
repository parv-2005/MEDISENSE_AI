"""Pydantic schemas shared by the API layer and services."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------- Auth
class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    name: str
    email: EmailStr
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------------------------------------------------------------- Reports
ReportStatus = Literal["uploaded", "extracting", "extracted", "analyzing", "analyzed", "failed"]


class ReportOut(BaseModel):
    id: str
    user_id: str
    original_filename: str
    stored_filename: str
    content_type: str
    size_bytes: int
    status: ReportStatus
    extraction_method: str | None = None
    page_count: int | None = None
    extracted_text: str | None = None
    has_analysis: bool = False
    error: str | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------- Analysis
FindingStatus = Literal["low", "normal", "high", "abnormal", "unknown"]
Urgency = Literal["routine", "soon", "urgent", "unknown"]

DEFAULT_DISCLAIMER = (
    "This AI-generated analysis is for informational purposes only and is not a substitute for "
    "professional medical advice, diagnosis, or treatment. Always consult a qualified clinician."
)


class Finding(BaseModel):
    parameter: str
    value: str = ""
    reference_range: str = ""
    status: FindingStatus = "unknown"
    explanation: str = ""

    @field_validator("status", mode="before")
    @classmethod
    def _normalise_status(cls, v):
        v = str(v or "").strip().lower()
        return v if v in ("low", "normal", "high", "abnormal", "unknown") else "unknown"


class ReportAnalysis(BaseModel):
    report_type: str = "Medical report"
    summary: str
    findings: list[Finding] = []
    abnormal_flags: list[str] = []
    insights: list[str] = []
    recommendations: list[str] = []
    urgency: Urgency = "unknown"
    disclaimer: str = DEFAULT_DISCLAIMER

    @field_validator("urgency", mode="before")
    @classmethod
    def _normalise_urgency(cls, v):
        v = str(v or "").strip().lower()
        return v if v in ("routine", "soon", "urgent", "unknown") else "unknown"

    @field_validator("disclaimer", mode="before")
    @classmethod
    def _default_disclaimer(cls, v):
        return v if isinstance(v, str) and v.strip() else DEFAULT_DISCLAIMER


class AnalysisOut(BaseModel):
    id: str
    report_id: str
    user_id: str
    model: str
    analysis: ReportAnalysis
    created_at: datetime


# ---------------------------------------------------------------- RAG
class QuestionIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class SourceChunk(BaseModel):
    chunk_index: int
    text: str
    score: float | None = None


class AnswerOut(BaseModel):
    id: str
    report_id: str
    question: str
    answer: str
    sources: list[SourceChunk]
    model: str
    created_at: datetime
