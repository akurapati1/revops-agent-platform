"""Standalone worker: consumes the Redis run queue and dispatches scheduled emails."""
import asyncio
import signal

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.jobs import scheduler_loop, worker_loop


async def main() -> None:
    s = get_settings()
    configure_logging(s.log_level)
    if not s.redis_url:
        raise SystemExit("REDIS_URL is required for the standalone worker")
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    await asyncio.gather(worker_loop(stop), scheduler_loop(stop))


if __name__ == "__main__":
    asyncio.run(main())
