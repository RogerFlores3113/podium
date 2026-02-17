import logging
import sys

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.database import engine, Base
from app.routers import documents, chat
from app.errors import global_exception_handler

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

# Add routers
app.include_router(documents.router)
app.include_router(chat.router)
app.add_exception_handler(Exception, global_exception_handler)


@app.get("/health")
async def health():
    return {"status": "ok"}