"""HTTP API for the semantic recommendation engine.

Run locally:   uvicorn api_server:app --port 8000
In Docker:     see Dockerfile (serves on $PORT)

The engine loads in a background thread at startup so the process answers health checks
immediately; /api/ready reports when recommendations can be served.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Path, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.config import Settings, load_engine_config, load_settings
from src.query_log import QueryLog
from src.recommender import Filters, RecommendationEngine, UnknownProductError

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("api")

QUERY_MAX_LENGTH = 200
TOP_K_MAX = 50
SIMILAR_MAX = 24
PRICE_MAX = 10_000_000


class EngineHolder:
    """Owns the engine and its loading state."""

    def __init__(self) -> None:
        self.engine: RecommendationEngine | None = None
        self.state: Literal["loading", "ready", "error"] = "loading"
        self.error: str | None = None
        self.started = time.time()

    def load(self, settings: Settings) -> None:
        try:
            self.engine = RecommendationEngine.load(settings)
            self.state = "ready"
            log.info("Engine ready in %.1fs (%s mode)", time.time() - self.started, self.engine.mode)
        except Exception as exc:  # surfaced through /api/ready
            log.exception("Engine failed to load")
            self.state, self.error = "error", f"{type(exc).__name__}: {exc}"

    def require(self) -> RecommendationEngine:
        if self.engine is None:
            detail = (
                "The recommendation engine is still loading." if self.state == "loading" else "Engine failed to load."
            )
            raise HTTPException(status_code=503, detail=detail, headers={"Retry-After": "10"})
        return self.engine


class RateLimiter:
    """Fixed one-minute window per client IP. In-process only: put a shared limiter (API
    gateway, reverse proxy) in front when running several replicas."""

    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self.hits: dict[str, deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        if self.per_minute <= 0:
            return True
        now = time.monotonic()
        with self.lock:
            window = self.hits[key]
            while window and now - window[0] > 60:
                window.popleft()
            if len(window) >= self.per_minute:
                return False
            window.append(now)
            if len(self.hits) > 10_000:  # bound memory under address churn
                for stale in [k for k, v in self.hits.items() if not v or now - v[-1] > 60]:
                    del self.hits[stale]
            return True


settings = load_settings()
holder = EngineHolder()
limiter = RateLimiter(settings.rate_limit_per_minute)
query_log = QueryLog(settings.query_log_path)


@asynccontextmanager
async def lifespan(_: FastAPI):
    threading.Thread(target=holder.load, args=(settings,), name="engine-loader", daemon=True).start()
    yield


app = FastAPI(
    title="Product Recommendation Engine API",
    version="2.0.0",
    description="Hybrid semantic + keyword product recommendations over an Amazon India catalog snapshot.",
    lifespan=lifespan,
)
if settings.allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    client = request.client.host if request.client else "unknown"
    limited = request.url.path.startswith("/api/") and request.url.path not in ("/api/health", "/api/ready")
    if limited and not limiter.allow(client):
        return JSONResponse(
            {"error": "Too many requests. Try again in a minute."},
            status_code=429,
            headers={"Retry-After": "60", "X-Request-ID": request_id},
        )
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    log.info(
        "%s %s %s %.1fms id=%s",
        request.method,
        request.url.path,
        response.status_code,
        (time.perf_counter() - started) * 1000,
        request_id,
    )
    return response


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
    message = f"{location}: {first.get('msg', 'invalid request')}" if location else first.get("msg", "invalid request")
    return JSONResponse({"error": message}, status_code=400)


@app.exception_handler(Exception)
async def unexpected_error(_: Request, exc: Exception):
    log.exception("Unhandled error", exc_info=exc)
    return JSONResponse({"error": "Internal server error."}, status_code=500)


# ---------------------------------------------------------------- schemas

PROFILES = tuple(load_engine_config()["profiles"])


class FiltersIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    department: str | None = Field(default=None, max_length=80)
    min_price: float | None = Field(default=None, ge=0, le=PRICE_MAX)
    max_price: float | None = Field(default=None, ge=0, le=PRICE_MAX)
    min_rating: float | None = Field(default=None, ge=0, le=5)

    @model_validator(mode="after")
    def check_range(self):
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise ValueError("min_price cannot exceed max_price")
        return self


class RecommendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=QUERY_MAX_LENGTH)
    profile: Literal[PROFILES] = "general"  # type: ignore[valid-type]
    top_k: int = Field(default=12, ge=1, le=TOP_K_MAX)
    filters: FiltersIn = Field(default_factory=FiltersIn)

    @model_validator(mode="after")
    def strip_query(self):
        self.query = self.query.strip()
        if not self.query:
            raise ValueError("query must not be blank")
        return self


# ---------------------------------------------------------------- routes


@app.get("/api/health")
def health():
    """Liveness: the process is up (the engine may still be loading)."""
    return {"status": "ok", "engine_state": holder.state}


@app.get("/api/ready")
def ready():
    """Readiness: recommendations can be served."""
    if holder.engine is None:
        body = {"status": holder.state, "error": holder.error, "uptime_s": round(time.time() - holder.started)}
        return JSONResponse(body, status_code=503, headers={"Retry-After": "10"})
    return {"status": "ready", "engine": holder.engine.status()}


@lru_cache(maxsize=1)
def catalog_meta() -> dict:
    with open(settings.catalog_meta_path, encoding="utf-8") as handle:
        return json.load(handle)


@app.get("/api/catalog")
def catalog():
    engine = holder.require()
    return {**catalog_meta(), "profiles": engine.profiles(), "engine": engine.status()}


@app.post("/api/recommend")
async def recommend(body: RecommendRequest):
    engine = holder.require()
    departments = set(engine.catalog.main_categories)
    if body.filters.department and body.filters.department not in departments:
        raise HTTPException(status_code=400, detail="filters.department is not a known department.")
    filters = Filters(**body.filters.model_dump())
    result = await run_in_threadpool(engine.recommend, body.query, body.profile, body.top_k, filters)
    query_log.write(result)
    return result


@app.get("/api/products/{asin}/similar")
async def similar(
    asin: Annotated[str, Path(pattern=r"^[A-Za-z0-9]{10}$")],
    k: Annotated[int, Query(ge=1, le=SIMILAR_MAX)] = 8,
):
    engine = holder.require()
    try:
        return await run_in_threadpool(engine.similar, asin.upper(), k)
    except UnknownProductError:
        raise HTTPException(status_code=404, detail=f"Unknown product {asin.upper()}.") from None


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api_server:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
