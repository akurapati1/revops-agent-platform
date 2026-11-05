# CLAUDE.md

Guidance for working in this repo.

## Commands

```bash
# Backend (Python 3.12+, from backend/ with .venv)
python -m pytest -q                       # all tests (SQLite + MockLLM, no network)
python -m pytest tests/test_orchestrator.py -k gate
ruff check . --fix
uvicorn app.main:app --reload --port 8000
alembic upgrade head                      # migrations
alembic revision --autogenerate -m "msg" # after changing app/models
python -m scripts.seed                    # demo@revops.dev / demo-password-123
python -m app.worker                      # only when REDIS_URL is set

# Frontend (from frontend/)
npm run dev | npm run build | npm run lint | npx tsc --noEmit

make help                                 # shortcuts for all of the above
```

## Architecture

Layering: `routers/` (thin HTTP) -> `services/` (business rules) -> `repositories/` + `models/`. Every query must be scoped by `org_id` (taken from the JWT via `deps.get_ctx`); never accept an org or user id from a request body.

- `app/agents/`: `base.py` (Agent, Tool, RunContext), `impl.py` (Researcher, Enricher, Personalizer, Sequencer, ReplyTriage), `schemas.py` (structured outputs), `tools.py` (domain lookup, ICP rubric, business-day scheduler), `registry.py` (agents and DAGs, `topo_order`), `orchestrator.py` (`execute_run`: creates a `RunStep` per agent, persists input/output/tokens/latency/cost, applies side effects in `_after_step`, pauses at `awaiting_approval`).
- `app/llm/`: `base.structured_call` validates with Pydantic and retries with error feedback; `mock.py` is deterministic and offline (`LLM_PROVIDER=mock`, default); `openrouter.py` is the real provider. Mock generators are keyed by agent name, so a new LLM agent needs a generator in `mock.py`.
- `app/services/approvals.py`: the human gate. Drafts are `Approval` rows (`pending -> approved -> sent`); approving sends immediately only if `scheduled_at` has passed, otherwise `jobs.scheduler_loop`/`dispatch_due` sends it. `refresh_run` moves the run to `scheduled`/`completed`/`rejected`.
- `app/services/jobs.py`: Redis list queue when `REDIS_URL` is set (worker in `app/worker.py`), otherwise in-process asyncio tasks (`drain()` is used by tests).
- `app/services/usage.py`: per-org monthly token limit, checked before every LLM step and at run creation (HTTP 402).
- `app/services/email.py`: `EmailProvider` protocol; console (default) and SMTP.
- Frontend: Next.js App Router in `frontend/src/app`; `(app)/` is the authenticated shell. `lib/api.ts` handles tokens (localStorage) and refresh; `lib/hooks.ts#useFetch` does polling. UI primitives live in `components/ui` (local shadcn-style). No `next/font/google`; system font stack.

## Conventions and gotchas

- Tests: `tests/conftest.py` sets env (temp SQLite, mock LLM, console mail) before importing the app. Use `make_account`, `make_lead`, `run_to_gate`; call `jobs.drain()` after anything that enqueues work.
- Schema changes need an Alembic migration (`test_alembic_migrations_apply_cleanly` runs `upgrade head` + `check`).
- Secrets come only from env; never commit `.env`. `JWT_SECRET` is mandatory in production.
- Adding an agent: schema in `agents/schemas.py`, class in `agents/impl.py`, register in `registry.py` (+ DAG), mock generator, tests.
