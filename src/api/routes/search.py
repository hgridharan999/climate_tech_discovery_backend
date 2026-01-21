"""Search API endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..models import SearchRequest, SearchResponse, InteractionLogRequest
from ...core.config import settings
from ...core.database import Database
from ...search.hybrid_search import HybridSearch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["search"])

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Singleton instances
_db: Optional[Database] = None
_search: Optional[HybridSearch] = None


def get_database() -> Database:
    """Get database instance."""
    global _db
    if _db is None:
        _db = Database(settings.database_path)
    return _db


def get_search_engine() -> HybridSearch:
    """Get search engine instance."""
    global _search
    if _search is None:
        _search = HybridSearch(get_database())
        try:
            _search.initialize()
        except Exception as e:
            logger.warning(f"Search initialization failed: {e}")
    return _search


@router.post("/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    search_engine: HybridSearch = Depends(get_search_engine),
):
    """
    Search for climate startups using hybrid semantic + keyword search.

    The search combines BERT-based semantic similarity with BM25 keyword matching
    using Reciprocal Rank Fusion for optimal results.
    """
    try:
        results = search_engine.search(
            query=request.query,
            top_k=request.top_k,
            vertical_filter=request.vertical_filter,
            founded_year_min=request.founded_year_min,
            founded_year_max=request.founded_year_max,
            min_funding_usd=request.min_funding_usd,
            enable_diversity=request.enable_diversity,
            enable_query_expansion=request.enable_query_expansion,
        )
        return SearchResponse(**results)
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/search", response_model=SearchResponse)
async def search_get(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    top_k: int = Query(default=20, ge=1, le=100),
    vertical: Optional[str] = Query(default=None, alias="vertical_filter"),
    year_min: Optional[int] = Query(default=None, alias="founded_year_min"),
    year_max: Optional[int] = Query(default=None, alias="founded_year_max"),
    min_funding: Optional[float] = Query(default=None, alias="min_funding_usd"),
    diversify: bool = Query(default=True, alias="enable_diversity"),
    expand: bool = Query(default=True, alias="enable_query_expansion"),
    search_engine: HybridSearch = Depends(get_search_engine),
):
    """Search via GET request for simpler integration."""
    try:
        results = search_engine.search(
            query=q,
            top_k=top_k,
            vertical_filter=vertical,
            founded_year_min=year_min,
            founded_year_max=year_max,
            min_funding_usd=min_funding,
            enable_diversity=diversify,
            enable_query_expansion=expand,
        )
        return SearchResponse(**results)
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/log-interaction")
async def log_interaction(
    request: InteractionLogRequest,
    db: Database = Depends(get_database),
):
    """Log a user interaction for click-through rate tracking."""
    try:
        db.log_interaction(
            query=request.query,
            startup_id=request.startup_id,
            rank=request.rank,
            action=request.action,
            session_id=request.session_id,
        )
        return {"status": "logged"}
    except Exception as e:
        logger.error(f"Error logging interaction: {e}")
        # Don't fail the request for logging errors
        return {"status": "error", "message": str(e)}
