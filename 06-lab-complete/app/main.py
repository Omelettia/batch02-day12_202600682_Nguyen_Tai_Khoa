"""
Production AI Agent for Day 12.

Combines 12-factor config, API key auth, Redis-backed rate limiting,
monthly cost guard, Redis conversation history, health/readiness checks,
structured JSON logs, and graceful shutdown behavior.
"""
import json
import logging
import signal
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import redis
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import CostGuard, estimate_tokens
from app.legal_rag import answer_legal_question
from app.rate_limiter import RateLimiter


logging.basicConfig(
    level=logging.DEBUG if settings.debug else getattr(logging, settings.log_level.upper(), logging.INFO),
    format='{"ts":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
INSTANCE_ID = settings.instance_id or f"agent-{uuid.uuid4().hex[:8]}"
HISTORY_TTL_SECONDS = 30 * 24 * 60 * 60
MAX_HISTORY_MESSAGES = 20

_is_ready = False
_request_count = 0
_error_count = 0
_redis: redis.Redis | None = None
_rate_limiter: RateLimiter | None = None
_cost_guard: CostGuard | None = None


def log_event(event: str, **fields) -> None:
    logger.info(json.dumps({"event": event, **fields}))


def get_redis() -> redis.Redis:
    if _redis is None:
        raise HTTPException(status_code=503, detail="Redis is not connected")
    return _redis


def save_message(user_id: str, role: str, content: str) -> list[dict]:
    client = get_redis()
    key = f"history:{user_id}"
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    client.rpush(key, json.dumps(message))
    client.ltrim(key, -MAX_HISTORY_MESSAGES, -1)
    client.expire(key, HISTORY_TTL_SECONDS)
    return load_history(user_id)


def load_history(user_id: str) -> list[dict]:
    client = get_redis()
    rows = client.lrange(f"history:{user_id}", 0, -1)
    return [json.loads(row) for row in rows]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready, _redis, _rate_limiter, _cost_guard
    log_event(
        "startup",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        instance_id=INSTANCE_ID,
    )
    try:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
        _redis.ping()
        _rate_limiter = RateLimiter(_redis, settings.rate_limit_per_minute)
        _cost_guard = CostGuard(_redis, settings.monthly_budget_usd)
        _is_ready = True
        log_event("ready", storage="redis")
    except Exception as exc:
        _is_ready = False
        logger.exception("Redis connection failed: %s", exc)

    yield

    _is_ready = False
    if _redis is not None:
        _redis.close()
    log_event("shutdown", instance_id=INSTANCE_ID)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count
    start = time.time()
    _request_count += 1
    try:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        if "server" in response.headers:
            del response.headers["server"]
        log_event(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            ms=round((time.time() - start) * 1000, 1),
        )
        return response
    except Exception:
        _error_count += 1
        raise


class AskRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=100)
    question: str = Field(..., min_length=1, max_length=2000)


class AskResponse(BaseModel):
    user_id: str
    question: str
    answer: str
    sources: list[dict]
    retrieval_source: str
    model: str
    history_length: int
    served_by: str
    timestamp: str


PUBLIC_DEMO_USER_ID = "public-demo"


@app.get("/", include_in_schema=False)
def root():
    return FileResponse("app/static/index.html")


@app.get("/api", tags=["Info"])
def api_info():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "endpoints": {
            "ask": "POST /ask (requires X-API-Key)",
            "demo_ask": "POST /demo/ask (public frontend route, rate limited)",
            "history": "GET /history/{user_id} (requires X-API-Key)",
            "health": "GET /health",
            "ready": "GET /ready",
        },
    }


def _run_agent(body: AskRequest, request: Request, storage_user_id: str, display_user_id: str) -> AskResponse:
    if not _is_ready or _rate_limiter is None or _cost_guard is None:
        raise HTTPException(status_code=503, detail="Service is not ready")

    rate_info = _rate_limiter.check(storage_user_id)
    input_tokens = estimate_tokens(body.question)
    _cost_guard.check_budget(storage_user_id, input_tokens, 0)

    save_message(storage_user_id, "user", body.question)
    history = load_history(storage_user_id)
    rag_result = answer_legal_question(body.question, history)
    answer = rag_result["answer"]
    output_tokens = estimate_tokens(answer)
    _cost_guard.check_budget(storage_user_id, input_tokens, output_tokens)
    _cost_guard.record_usage(storage_user_id, input_tokens, output_tokens)
    history = save_message(storage_user_id, "assistant", answer)

    log_event(
        "agent_call",
        user_id=storage_user_id,
        q_len=len(body.question),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        rate_remaining=rate_info["remaining"],
        client=str(request.client.host) if request.client else "unknown",
    )

    return AskResponse(
        user_id=display_user_id,
        question=body.question,
        answer=answer,
        sources=rag_result["sources"],
        retrieval_source=rag_result["retrieval_source"],
        model=rag_result.get("model", "local-day9-legal-rag"),
        history_length=len(history),
        served_by=INSTANCE_ID,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
def ask_agent(body: AskRequest, request: Request, _api_key: str = Depends(verify_api_key)):
    return _run_agent(body, request, body.user_id, body.user_id)


@app.post("/demo/ask", response_model=AskResponse, tags=["Frontend"])
def demo_ask(body: AskRequest, request: Request):
    return _run_agent(body, request, PUBLIC_DEMO_USER_ID, body.user_id)


@app.get("/history/{user_id}", tags=["Agent"])
def get_history(user_id: str, _api_key: str = Depends(verify_api_key)):
    return {"user_id": user_id, "messages": load_history(user_id)}


@app.delete("/history/{user_id}", tags=["Agent"])
def clear_history(user_id: str, _api_key: str = Depends(verify_api_key)):
    get_redis().delete(f"history:{user_id}")
    return {"deleted": user_id}


@app.get("/health", tags=["Operations"])
def health():
    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.environment,
        "instance_id": INSTANCE_ID,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Operations"])
def ready():
    if not _is_ready:
        raise HTTPException(status_code=503, detail="Not ready")
    try:
        get_redis().ping()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Redis not ready: {exc}") from exc
    return {"ready": True, "storage": "redis", "instance_id": INSTANCE_ID}


@app.get("/metrics", tags=["Operations"])
def metrics(_api_key: str = Depends(verify_api_key)):
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
        "monthly_budget_usd": settings.monthly_budget_usd,
        "rate_limit_per_minute": settings.rate_limit_per_minute,
    }


def _handle_signal(signum, _frame):
    global _is_ready
    _is_ready = False
    log_event("signal", signum=signum, graceful_shutdown_seconds=30)


signal.signal(signal.SIGTERM, _handle_signal)


if __name__ == "__main__":
    log_event("run_server", host=settings.host, port=settings.port)
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
