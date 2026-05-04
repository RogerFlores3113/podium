from fastapi import Request
from fastapi.responses import JSONResponse
import logging

from app.config import CORS_ORIGINS

logger = logging.getLogger(__name__)


async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    # Explicitly add CORS headers so the browser can read this response even
    # when the exception bypasses CORSMiddleware's send wrapper (e.g. exceptions
    # caught by Starlette's ServerErrorMiddleware before CORS can intercept them).
    origin = request.headers.get("origin", "")
    headers = {}
    if origin in CORS_ORIGINS:
        headers["access-control-allow-origin"] = origin
        headers["access-control-allow-credentials"] = "true"
        headers["vary"] = "Origin"
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check logs for details."},
        headers=headers,
    )