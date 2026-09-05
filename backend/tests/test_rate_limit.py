import unittest

from redis.exceptions import RedisError

from app.exceptions import RateLimitExceeded, RateLimitUnavailable
from app.services.rate_limit import RedisGlobalQueryRateLimiter


class RedisGlobalQueryRateLimiterTest(unittest.TestCase):
    def test_allows_requests_until_limit(self):
        redis = FakeRedis()
        limiter = RedisGlobalQueryRateLimiter(redis, limit=2, window_seconds=3600)

        first = limiter.check()
        second = limiter.check()

        self.assertTrue(first.allowed)
        self.assertEqual(first.remaining, 1)
        self.assertEqual(second.remaining, 0)
        self.assertEqual(redis.expire_calls, [("rate:global:query", 3600)])

    def test_blocks_after_limit_with_retry_after(self):
        redis = FakeRedis(ttl=120)
        limiter = RedisGlobalQueryRateLimiter(redis, limit=1, window_seconds=3600)

        limiter.check()
        with self.assertRaises(RateLimitExceeded) as ctx:
            limiter.check()

        self.assertEqual(ctx.exception.retry_after_seconds, 120)

    def test_raises_unavailable_when_redis_fails(self):
        limiter = RedisGlobalQueryRateLimiter(FailingRedis(), limit=1)

        with self.assertRaises(RateLimitUnavailable):
            limiter.check()


class FakeRedis:
    def __init__(self, ttl=3600):
        self.count = 0
        self.ttl_value = ttl
        self.expire_calls = []

    def incr(self, key):
        self.count += 1
        return self.count

    def expire(self, key, seconds):
        self.expire_calls.append((key, seconds))

    def ttl(self, key):
        return self.ttl_value


class FailingRedis:
    def incr(self, key):
        raise RedisError("redis down")


if __name__ == "__main__":
    unittest.main()
