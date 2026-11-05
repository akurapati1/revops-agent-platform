import csv
import io

from email_validator import EmailNotValidError, validate_email
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, Conflict
from app.models import Lead
from app.repositories import leads as repo
from app.schemas.api import ImportResult, LeadIn, LeadUpdate

MAX_ROWS = 5000
MAX_BYTES = 2_000_000
ALIASES = {
    "email": "email", "email_address": "email", "e_mail": "email", "work_email": "email",
    "first_name": "first_name", "firstname": "first_name", "given_name": "first_name",
    "last_name": "last_name", "lastname": "last_name", "surname": "last_name", "family_name": "last_name",
    "company": "company", "company_name": "company", "organization": "company", "account": "company",
    "title": "title", "job_title": "title", "role": "title", "position": "title",
    "website": "website", "domain": "website", "url": "website", "company_website": "website",
    "linkedin": "linkedin_url", "linkedin_url": "linkedin_url", "linkedin_profile": "linkedin_url",
    "notes": "notes", "note": "notes",
}


async def create(session: AsyncSession, org_id: str, data: LeadIn, source: str = "manual") -> Lead:
    if await repo.by_email(session, org_id, data.email):
        raise Conflict("A lead with this email already exists")
    lead = Lead(org_id=org_id, source=source, **data.model_dump())
    session.add(lead)
    await session.flush()
    return lead


async def update(session: AsyncSession, org_id: str, lead_id: str, data: LeadUpdate) -> Lead:
    lead = await repo.get(session, org_id, lead_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(lead, k, v)
    return lead


async def delete(session: AsyncSession, org_id: str, lead_id: str) -> None:
    await session.delete(await repo.get(session, org_id, lead_id))


async def import_csv(session: AsyncSession, org_id: str, raw: bytes) -> ImportResult:
    if len(raw) > MAX_BYTES:
        raise AppError("CSV is too large (max 2 MB)", code="csv_too_large")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AppError("CSV must be UTF-8 encoded", code="csv_encoding") from exc
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise AppError("CSV has no header row", code="csv_empty")
    mapping = {}
    for h in reader.fieldnames:
        key = (h or "").strip().lower().replace(" ", "_").replace("-", "_")
        if key in ALIASES:
            mapping[h] = ALIASES[key]
    if "email" not in mapping.values():
        raise AppError("CSV needs an 'email' column", code="csv_missing_email")

    created = skipped = 0
    errors: list[dict] = []
    seen: set[str] = set()
    for i, row in enumerate(reader, start=2):
        if i - 1 > MAX_ROWS:
            errors.append({"row": i, "error": f"row limit of {MAX_ROWS} reached; remaining rows ignored"})
            break
        rec = {mapping[h]: (v or "").strip() for h, v in row.items() if h in mapping and isinstance(v, str)}
        try:
            email = validate_email(rec.get("email", ""), check_deliverability=False).normalized.lower()
        except EmailNotValidError as exc:
            errors.append({"row": i, "error": f"invalid email: {exc}"})
            continue
        if email in seen or await repo.by_email(session, org_id, email):
            skipped += 1
            continue
        seen.add(email)
        rec["email"] = email
        try:
            data = LeadIn(**rec)
        except ValueError as exc:
            errors.append({"row": i, "error": str(exc).splitlines()[0]})
            continue
        session.add(Lead(org_id=org_id, source="csv", **data.model_dump()))
        created += 1
    await session.flush()
    return ImportResult(created=created, skipped=skipped, errors=errors[:50])
