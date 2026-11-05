"""Run job dispatch: Redis list queue when REDIS_URL is set, in-process asyncio tasks otherwise."""
import asyncio

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("jobs")
QUEUE_KEY = "revops:runs"
_tasks: set[asyncio.Task] = set()


def _redis():
    import redis.asyncio as aioredis

    return aioredis.from_url(get_settings().redis_url)


async def enqueue_run(run_id: str) -> None:
    from app.agents.orchestrator import execute_run

    if get_settings().redis_url:
        r = _redis()
        try:
            await r.lpush(QUEUE_KEY, run_id)
        finally:
            await r.aclose()
        return
    task = asyncio.create_task(execute_run(run_id), name=f"run-{run_id}")
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def drain() -> None:
    """Wait for in-process jobs (used by tests and graceful shutdown)."""
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)


async def worker_loop(stop: asyncio.Event) -> None:
    from app.agents.orchestrator import execute_run

    r = _redis()
    log.info("worker.started")
    try:
        while not stop.is_set():
            item = await r.brpop([QUEUE_KEY], timeout=2)
            if item:
                run_id = item[1].decode() if isinstance(item[1], bytes) else item[1]
                try:
                    await execute_run(run_id)
                except Exception:
                    log.exception("worker.run_failed", extra={"run_id": run_id})
    finally:
        await r.aclose()


async def scheduler_loop(stop: asyncio.Event) -> None:
    """Periodically send approved emails whose scheduled time has arrived."""
    from app.db import SessionLocal
    from app.services import approvals

    interval = get_settings().scheduler_interval_seconds
    while not stop.is_set():
        try:
            async with SessionLocal() as s:
                n = await approvals.dispatch_due(s)
                await s.commit()
                if n:
                    log.info("scheduler.dispatched", extra={"count": n})
        except Exception:
            log.exception("scheduler.error")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            pass
