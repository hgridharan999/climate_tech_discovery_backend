"""Statistics and health check endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, BackgroundTasks

from ..models import StatsResponse, HealthResponse, EvaluationResponse
from ...core.config import settings
from ...core.database import Database
from ...search.hybrid_search import HybridSearch
from ...evaluation.evaluator import SearchEvaluator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stats"])

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


@router.get("/health", response_model=HealthResponse)
async def health_check(
    db: Database = Depends(get_database),
    search_engine: HybridSearch = Depends(get_search_engine),
):
    """Health check endpoint."""
    try:
        startup_count = db.get_startup_count()
        db_connected = True
    except Exception:
        startup_count = 0
        db_connected = False

    return HealthResponse(
        status="healthy" if db_connected else "degraded",
        version="1.0.0",
        database_connected=db_connected,
        search_initialized=search_engine.is_initialized,
        startup_count=startup_count,
    )


@router.get("/api/stats", response_model=StatsResponse)
async def get_stats(
    db: Database = Depends(get_database),
):
    """Get database statistics."""
    stats = db.get_stats()
    return StatsResponse(**stats)


@router.get("/api/evaluate", response_model=EvaluationResponse)
async def evaluate_search(
    search_engine: HybridSearch = Depends(get_search_engine),
):
    """Run evaluation on test queries and return relevance metrics."""
    evaluator = SearchEvaluator(search_engine)
    results = evaluator.evaluate_test_queries()
    return EvaluationResponse(**results)


async def _run_rescrape(db: Database, search_engine: HybridSearch):
    """Background task: scrape new startup data and rebuild indexes."""
    try:
        from ...data.scraper import ClimateScraper
        async with ClimateScraper(db) as scraper:
            count = await scraper.scrape_all_sources()
            logger.info(f"Rescrape complete: {count} startups in database")
        search_engine.rebuild_index()
        logger.info("Search indexes rebuilt after rescrape")
    except Exception as e:
        logger.error(f"Rescrape failed: {e}")


@router.post("/api/admin/rescrape")
async def rescrape(
    background_tasks: BackgroundTasks,
    db: Database = Depends(get_database),
    search_engine: HybridSearch = Depends(get_search_engine),
):
    """
    Trigger a background rescrape of all startup sources and rebuild indexes.
    The API continues serving requests while the scrape runs in the background.
    """
    background_tasks.add_task(_run_rescrape, db, search_engine)
    return {"status": "rescrape started", "message": "Check /health for updated startup_count"}
