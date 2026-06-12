from datetime import datetime, timezone

from fastapi import HTTPException
from redis import Redis


PRICE_PER_1K_INPUT_TOKENS = 0.00015
PRICE_PER_1K_OUTPUT_TOKENS = 0.0006


def estimate_tokens(text: str) -> int:
    return max(1, len(text.split()) * 2)


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens / 1000 * PRICE_PER_1K_INPUT_TOKENS
        + output_tokens / 1000 * PRICE_PER_1K_OUTPUT_TOKENS
    )


class CostGuard:
    """Monthly per-user budget guard backed by Redis."""

    def __init__(self, redis_client: Redis, monthly_budget_usd: float = 10.0):
        self.redis = redis_client
        self.monthly_budget_usd = monthly_budget_usd

    def _key(self, user_id: str) -> str:
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        return f"budget:{user_id}:{month}"

    def check_budget(self, user_id: str, input_tokens: int, output_tokens: int) -> None:
        key = self._key(user_id)
        current = float(self.redis.get(key) or 0)
        estimated = estimate_cost(input_tokens, output_tokens)
        if current + estimated > self.monthly_budget_usd:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "Monthly budget exceeded",
                    "used_usd": round(current, 6),
                    "estimated_usd": round(estimated, 6),
                    "budget_usd": self.monthly_budget_usd,
                    "resets": "first day of next UTC month",
                },
            )

    def record_usage(self, user_id: str, input_tokens: int, output_tokens: int) -> float:
        cost = estimate_cost(input_tokens, output_tokens)
        key = self._key(user_id)
        total = self.redis.incrbyfloat(key, cost)
        self.redis.expire(key, 32 * 24 * 60 * 60)
        return float(total)
