from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.database import engine, Base
from app.routers import documents



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create pgvector extension and tables on startup
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="AI Assistant Platform", version="0.1.0", lifespan=lifespan)

# After the app = FastAPI(...) line:
app.include_router(documents.router)

@app.get("/health")
async def health():
    return {"status": "ok"}