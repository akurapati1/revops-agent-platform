"""Fixed-window rate limiter: Redis when REDIS_URL is set, in-process otherwise."""
import time
from collections import defaultdict

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import AppError


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"


class MemoryLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))

    async def hit(self, key: str, limit: int, window: int = 60) -> bool:
        bucket = int(time.time() // window)
        b, n = self._hits[key]
        if b != bucket:
            b, n = bucket, 0
        n += 1
        self._hits[key] = (b, n)
        if len(self._hits) > 50_000:
            self._hits.clear()
        return n <= limit

    def reset(self) -> None:
        self._hits.clear()


class RedisLimiter:
    def __init__(self, url: str) -> None:
        import redis.asyncio as aioredis

        self._r = aioredis.from_url(url)

    async def hit(self, key: str, limit: int, window: int = 60) -> bool:
        bucket = int(time.time() // window)
        k = f"rl:{key}:{bucket}"
        try:
            n = await self._r.incr(k)
            if n == 1:
                await self._r.expire(k, window + 1)
            return n <= limit
        except Exception:  # fail open if redis is down
            return True


_limiter: MemoryLimiter | RedisLimiter | None = None


def get_limiter() -> MemoryLimiter | RedisLimiter:
    global _limiter
    if _limiter is None:
        s = get_settings()
        _limiter = RedisLimiter(s.redis_url) if s.redis_url else MemoryLimiter()
    return _limiter


def _ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def global_rate_limit(request: Request) -> None:
    if request.url.path in ("/health", "/ready"):
        return
    ok = await get_limiter().hit(f"g:{_ip(request)}", get_settings().rate_limit_per_minute)
    if not ok:
        raise RateLimited("Too many requests")


async def auth_rate_limit(request: Request) -> None:
    ok = await get_limiter().hit(f"a:{_ip(request)}:{request.url.path}", get_settings().auth_rate_limit_per_minute)
    if not ok:
        raise RateLimited("Too many authentication attempts")
