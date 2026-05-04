import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings, CORS_ORIGINS
from app.database import engine, async_session
from app.errors import global_exception_handler
from app.limiter import limiter
from app.routers import documents, chat, keys, memories, guest
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware


logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.guest_jwt_secret:
        logger.critical(
            "GUEST_JWT_SECRET is not set — guest sessions will return 503 until this is configured"
        )

    # Create pgvector extension on startup
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    # Create shared Redis pool for memory extraction scheduling
    from arq import create_pool
    from arq.connections import RedisSettings
    app.state.redis_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))

    yield

    await app.state.redis_pool.aclose()


app = FastAPI(title="AI Assistant Platform", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(guest.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(keys.router)
app.include_router(memories.router)
app.add_exception_handler(Exception, global_exception_handler)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.get("/health")
async def health():
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "detail": str(e)},
        )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded. Please slow down.",
            "retry_after": str(exc.detail),
        },
    )
