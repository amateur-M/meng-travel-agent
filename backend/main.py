"""CoupleTrip Backend — FastAPI application factory.

V4/P1: this module used to be a 673-line monolith that mixed five concerns
(routing, SSE framing, graph orchestration, the stream bus, storage calls).
Those now live in :mod:`api` (routers) and :mod:`services` (sse,
plan_pipeline). What remains here is pure assembly: logging, metrics, rate
limiting, CORS, router registration and the startup storage probe.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from api import chat, health, plan, profile
from api.rate_limit import limiter
from config.settings import settings
from logging_config import configure_logging
from services.conversation_store import conversation_store
from services.storage import plan_store

# P3.2: 结构化日志（JSON），在 app 创建前配置以覆盖全部模块
configure_logging(json_logs=settings.json_logs)

logger = logging.getLogger("coupletrip")


# ── T0.4: Storage visibility ─────────────────────────────────────
#
# The V2 persistence layer degraded silently: with the database unreachable,
# every PlanStore call returned None/False/[] and the only trace was a
# warning, so "the feature is broken" looked identical to "nothing was
# saved yet".  Storage state is now probed once at startup and exposed on
# /health, so a misconfiguration is impossible to miss.

async def _report_storage_status() -> None:
    """Log the real connectivity of every storage backend, once, at startup."""
    pg = await asyncio.to_thread(plan_store.health)
    if pg["connected"]:
        logger.info("storage: postgres connected (plans)")
    else:
        logger.error(
            "storage: postgres UNAVAILABLE — plan persistence is DISABLED (reason: %s)",
            pg["error"],
        )

    chat_store = await conversation_store.health()
    if chat_store["connected"]:
        logger.info("storage: postgres connected (chat history)")
    else:
        logger.error(
            "storage: chat history will NOT persist (reason: %s)",
            chat_store["error"],
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    await _report_storage_status()
    yield


def create_app() -> FastAPI:
    """Assemble the FastAPI application (middleware, metrics, routers)."""
    application = FastAPI(
        title="CoupleTrip API",
        description="AI-powered couple travel planning agent",
        version="0.3.0",
        lifespan=lifespan,
    )

    # P3.2: Prometheus metrics 暴露 /metrics
    Instrumentator().instrument(application).expose(
        application, endpoint="/metrics", include_in_schema=False
    )

    # P3.1 限流：中间件始终挂载。RATE_LIMIT_ENABLED=false（默认）时不实际计数，
    # 避免测试高频请求触发 429；生产环境设 true 开启。limiter 实例在
    # api.rate_limit 中创建，供各 router 的 @limiter.limit 装饰器共享。
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    application.add_middleware(SlowAPIMiddleware)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health.router)
    application.include_router(chat.router)
    application.include_router(profile.router)
    application.include_router(plan.router)

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
