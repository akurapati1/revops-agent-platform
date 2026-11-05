import asyncio
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging, get_logger
from app.core.ratelimit import global_rate_limit
from app.db import create_all
from app.routers import auth, leads, misc, orgs, runs
from app.services import jobs

log = get_logger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    configure_logging(s.log_level)
    if s.auto_create_tables:
        await create_all()
    stop = asyncio.Event()
    task = None
    if s.run_scheduler and not s.redis_url:
        task = asyncio.create_task(jobs.scheduler_loop(stop))
    log.info("api.started", extra={"llm": s.llm_provider, "email": s.email_provider, "queue": "redis" if s.redis_url else "in-process"})
    yield
    stop.set()
    if task:
        await task
    await jobs.drain()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title=s.app_name, version="1.0.0", lifespan=lifespan, dependencies=[Depends(global_rate_limit)])
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origin_list, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])

    @app.middleware("http")
    async def access_log(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        if request.url.path not in ("/health", "/ready"):
            log.info("http.request", extra={"method": request.method, "path": request.url.path, "status": response.status_code,
                                            "ms": round((time.perf_counter() - started) * 1000, 1), "request_id": rid})
        return response

    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message, "code": exc.code})

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        errs = [{"loc": [str(x) for x in e["loc"]], "msg": e["msg"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": "Validation failed", "code": "validation_error", "errors": errs})

    for r in (misc.router, auth.router, orgs.router, leads.router, runs.router):
        app.include_router(r)
    return app


app = create_app()
