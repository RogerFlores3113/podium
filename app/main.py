import logging
import sys

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import engine, Base
from app.routers import documents, chat, keys
from app.errors import global_exception_handler
from sqlalchemy import text 
from app.database import async_session
from app.config import settings


from app.limiter import limiter
from slowapi.errors import RateLimitExceeded 
from slowapi.middleware import SlowAPIMiddleware 



logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger=logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create pgvector extension and tables on startup
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    yield


app = FastAPI(title="AI Assistant Platform", version="0.1.0", lifespan=lifespan)

# Replace the existing CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  
        "https://podium-beta.vercel.app", # ADD ANY OTHER URLS HERE IF "FAILED TO GET A RESPONSE: IS THE BACKEND RUNNING?" 
        "http://localhost:8000"   
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Add routers
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(keys.router)
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
        }
    )
