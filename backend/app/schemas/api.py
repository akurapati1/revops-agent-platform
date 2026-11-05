from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- auth ----
class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default="", max_length=200)
    org_name: str | None = Field(default=None, max_length=200)
    invite_token: str | None = None

    @field_validator("email")
    @classmethod
    def lower(cls, v: str) -> str:
        return v.lower()


class LoginIn(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def lower(cls, v: str) -> str:
        return v.lower()


class RefreshIn(BaseModel):
    refresh_token: str


class SwitchOrgIn(BaseModel):
    org_id: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(ORM):
    id: str
    email: str
    name: str
    avatar_url: str | None = None


class OrgBrief(ORM):
    id: str
    name: str
    slug: str
    role: str


class MeOut(BaseModel):
    user: UserOut
    org: OrgBrief | None
    orgs: list[OrgBrief]


# ---- orgs ----
class ICP(BaseModel):
    industries: list[str] = Field(default_factory=list)
    min_employees: int | None = Field(default=None, ge=1)
    max_employees: int | None = Field(default=None, ge=1)
    regions: list[str] = Field(default_factory=list)


class OrgSettings(BaseModel):
    icp: ICP = Field(default_factory=ICP)
    sender_name: str = Field(default="", max_length=100)
    product_pitch: str = Field(default="", max_length=500)


class OrgOut(BaseModel):
    id: str
    name: str
    slug: str
    role: str
    monthly_token_limit: int
    settings: OrgSettings
    webhook_token: str | None = None  # only for admins


class OrgUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    monthly_token_limit: int | None = Field(default=None, ge=1000, le=1_000_000_000)
    settings: OrgSettings | None = None


class MemberOut(BaseModel):
    user_id: str
    email: str
    name: str
    role: str
    created_at: datetime


class MemberRoleIn(BaseModel):
    role: Literal["admin", "member", "owner"]


class InviteIn(BaseModel):
    email: EmailStr
    role: Literal["admin", "member"] = "member"


class InviteOut(ORM):
    id: str
    email: str
    role: str
    token: str
    accepted: bool
    created_at: datetime


class AcceptInviteIn(BaseModel):
    token: str


# ---- leads ----
class LeadIn(BaseModel):
    email: EmailStr
    first_name: str = Field(default="", max_length=100)
    last_name: str = Field(default="", max_length=100)
    company: str = Field(default="", max_length=200)
    title: str = Field(default="", max_length=200)
    website: str = Field(default="", max_length=300)
    linkedin_url: str = Field(default="", max_length=300)
    notes: str = Field(default="", max_length=5000)

    @field_validator("email")
    @classmethod
    def lower(cls, v: str) -> str:
        return v.lower()


class LeadUpdate(BaseModel):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    company: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, max_length=200)
    website: str | None = Field(default=None, max_length=300)
    linkedin_url: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=5000)


class LeadOut(ORM):
    id: str
    email: str
    first_name: str
    last_name: str
    company: str
    title: str
    website: str
    linkedin_url: str
    notes: str
    source: str
    status: str
    icp_score: int | None
    created_at: datetime
    updated_at: datetime


class LeadDetail(LeadOut):
    brief: dict[str, Any] | None
    firmographics: dict[str, Any] | None


class LeadPage(BaseModel):
    items: list[LeadOut]
    total: int
    limit: int
    offset: int


class ImportResult(BaseModel):
    created: int
    skipped: int
    errors: list[dict[str, Any]]


# ---- runs ----
class RunCreate(BaseModel):
    campaign: str = Field(default="", max_length=200)


class BulkRunCreate(BaseModel):
    lead_ids: list[str] = Field(min_length=1, max_length=200)
    campaign: str = Field(default="", max_length=200)


class StepOut(ORM):
    id: str
    seq: int
    agent: str
    status: str
    model: str | None
    input: dict[str, Any]
    output: dict[str, Any] | None
    tool_calls: list[Any]
    error: str | None
    attempts: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    started_at: datetime | None
    finished_at: datetime | None


class RunOut(ORM):
    id: str
    lead_id: str
    kind: str
    status: str
    campaign: str
    error: str | None
    total_tokens: int
    total_cost_usd: float
    created_at: datetime
    finished_at: datetime | None
    lead_email: str | None = None
    lead_company: str | None = None


class RunDetail(RunOut):
    steps: list[StepOut]
    approvals: list["ApprovalOut"]


class ApprovalOut(ORM):
    id: str
    run_id: str
    lead_id: str
    kind: str
    step_number: int
    to_email: str
    subject: str
    body: str
    scheduled_at: datetime
    status: str
    reviewed_at: datetime | None
    sent_at: datetime | None
    error: str | None
    created_at: datetime
    lead_name: str | None = None
    lead_company: str | None = None


class ApprovalEdit(BaseModel):
    subject: str | None = Field(default=None, min_length=1, max_length=300)
    body: str | None = Field(default=None, min_length=1)


class ReplyIn(BaseModel):
    body: str = Field(min_length=1, max_length=20000)


class WebhookReplyIn(BaseModel):
    from_email: EmailStr
    body: str = Field(min_length=1, max_length=20000)


class ReplyOut(ORM):
    id: str
    lead_id: str
    run_id: str | None
    source: str
    body: str
    classification: str | None
    confidence: float | None
    summary: str | None
    created_at: datetime


RunDetail.model_rebuild()
