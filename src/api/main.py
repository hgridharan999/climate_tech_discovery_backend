"""Main FastAPI application."""

import sys
import os
from pathlib import Path

# Ensure src directory is in Python path
root_dir = Path(__file__).parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from ..core.config import settings
from ..core.logging import setup_logging
from .routes import search_router, startups_router, stats_router

# Set up logging
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Climate Search API starting up...")
    logger.info(f"Allowed origins: {settings.allowed_origins_list}")
    yield
    logger.info("Climate Search API shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Climate Tech Search API",
    description="AI-powered search engine for climate technology startups",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(search_router)
app.include_router(startups_router)
app.include_router(stats_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Climate Tech Search API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
