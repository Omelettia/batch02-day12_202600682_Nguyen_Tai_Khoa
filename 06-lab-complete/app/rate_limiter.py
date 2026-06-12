import time

from fastapi import HTTPException
from redis import Redis


class RateLimiter:
    """Redis sliding-window rate limiter."""

    def __init__(self, redis_client: Redis, max_requests: int = 10, window_seconds: int = 60):
        self.redis = redis_client
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def check(self, user_id: str) -> dict:
        now = time.time()
        key = f"rate:{user_id}"
        window_start = now - self.window_seconds

        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        _, current = pipe.execute()

        if current >= self.max_requests:
            oldest = self.redis.zrange(key, 0, 0, withscores=True)
            retry_after = self.window_seconds
            if oldest:
                retry_after = max(1, int(oldest[0][1] + self.window_seconds - now) + 1)
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "limit": self.max_requests,
                    "window_seconds": self.window_seconds,
                    "retry_after_seconds": retry_after,
                },
                headers={
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": str(retry_after),
                },
            )

        member = f"{now}:{time.perf_counter_ns()}"
        pipe = self.redis.pipeline()
        pipe.zadd(key, {member: now})
        pipe.expire(key, self.window_seconds + 5)
        pipe.execute()

        return {
            "limit": self.max_requests,
            "remaining": self.max_requests - current - 1,
            "reset_at": int(now + self.window_seconds),
        }
