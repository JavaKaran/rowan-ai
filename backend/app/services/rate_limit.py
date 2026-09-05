import os
from dataclasses import dataclass
from functools import lru_cache

from redis import Redis
from redis.exceptions import RedisError

from app.exceptions import RateLimitExceeded, RateLimitUnavailable

DEFAULT_REDIS_URL = "redis://redis:6379/0"
DEFAULT_GLOBAL_QUERY_LIMIT = 50
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60 * 60


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: int


class RedisGlobalQueryRateLimiter:
    def __init__(
        self,
        redis_client: Redis,
        limit: int = DEFAULT_GLOBAL_QUERY_LIMIT,
        window_seconds: int = DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
        key: str = "rate:global:query",
    ):
        self.redis_client = redis_client
        self.limit = limit
        self.window_seconds = window_seconds
        self.key = key

    def check(self) -> RateLimitDecision:
        try:
            count = self.redis_client.incr(self.key)
            if count == 1:
                self.redis_client.expire(self.key, self.window_seconds)

            ttl = self.redis_client.ttl(self.key)
        except RedisError as exc:
            raise RateLimitUnavailable(
                "Rate limit service is unavailable. Please try again shortly."
            ) from exc

        retry_after_seconds = ttl if ttl and ttl > 0 else self.window_seconds
        remaining = max(self.limit - count, 0)

        if count > self.limit:
            raise RateLimitExceeded(
                "Too many queries are running on this deployment. Please try again later.",
                retry_after_seconds=retry_after_seconds,
            )

        return RateLimitDecision(
            allowed=True,
            limit=self.limit,
            remaining=remaining,
            retry_after_seconds=retry_after_seconds,
        )


@lru_cache(maxsize=1)
def get_query_rate_limiter() -> RedisGlobalQueryRateLimiter:
    redis_url = os.getenv("REDIS_URL", DEFAULT_REDIS_URL)
    limit = int(os.getenv("GLOBAL_QUERY_RATE_LIMIT", str(DEFAULT_GLOBAL_QUERY_LIMIT)))
    window_seconds = int(
        os.getenv("GLOBAL_QUERY_RATE_WINDOW_SECONDS", str(DEFAULT_RATE_LIMIT_WINDOW_SECONDS))
    )
    return RedisGlobalQueryRateLimiter(
        Redis.from_url(redis_url, decode_responses=True),
        limit=limit,
        window_seconds=window_seconds,
    )
