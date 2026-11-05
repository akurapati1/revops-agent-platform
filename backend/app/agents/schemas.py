"""Structured outputs for every agent."""
from typing import Literal

from pydantic import BaseModel, Field


class ResearchBrief(BaseModel):
    company_summary: str
    what_they_do: str
    person_summary: str
    recent_signals: list[str] = Field(default_factory=list, max_length=8)
    pain_points: list[str] = Field(default_factory=list, max_length=8)
    talking_points: list[str] = Field(default_factory=list, max_length=8)
    sources: list[str] = Field(default_factory=list, max_length=8)


class Enrichment(BaseModel):
    industry: str
    employee_estimate: int = Field(ge=1)
    region: str
    funding_stage: str = "unknown"
    tech_stack: list[str] = Field(default_factory=list, max_length=12)
    buying_persona: Literal["economic_buyer", "champion", "influencer", "end_user", "unknown"] = "unknown"
    icp_score: int = Field(ge=0, le=100, default=0)
    fit_tier: Literal["A", "B", "C"] = "C"
    icp_reasoning: str = ""


class EmailStep(BaseModel):
    step_number: int = Field(ge=1, le=6)
    delay_days: int = Field(ge=0, le=30)
    angle: str = ""
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)


class EmailSequence(BaseModel):
    steps: list[EmailStep] = Field(min_length=1, max_length=5)


class ScheduledStep(BaseModel):
    step_number: int
    scheduled_at: str
    subject: str
    body: str


class Schedule(BaseModel):
    steps: list[ScheduledStep]
    timezone: str = "UTC"


class TriageResult(BaseModel):
    classification: Literal["interested", "objection", "out_of_office", "unsubscribe", "other"]
    confidence: float = Field(ge=0, le=1)
    summary: str
    objection_type: str | None = None
    return_date: str | None = None
    suggested_action: str
    draft_reply: str | None = None
