"""Startup API endpoints."""

import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends, Query

from ..models import StartupResponse, VerticalInfo, VerticalsResponse
from ...core.config import settings
from ...core.database import Database
from ...data.category_mapper import CategoryMapper

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["startups"])

# Singleton instances
_db: Optional[Database] = None
_category_mapper: Optional[CategoryMapper] = None


def get_database() -> Database:
    """Get database instance."""
    global _db
    if _db is None:
        _db = Database(settings.database_path)
    return _db


def get_category_mapper() -> CategoryMapper:
    """Get category mapper instance."""
    global _category_mapper
    if _category_mapper is None:
        _category_mapper = CategoryMapper()
    return _category_mapper


@router.get("/startups/{startup_id}", response_model=StartupResponse)
async def get_startup(
    startup_id: int,
    db: Database = Depends(get_database),
):
    """Get a specific startup by ID."""
    startup = db.get_startup_by_id(startup_id)
    if not startup:
        raise HTTPException(status_code=404, detail="Startup not found")
    return StartupResponse(**startup)


@router.get("/startups", response_model=List[StartupResponse])
async def list_startups(
    vertical: Optional[str] = Query(default=None, description="Filter by vertical"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Database = Depends(get_database),
):
    """List startups with optional filtering."""
    if vertical:
        startups = db.get_startups_by_vertical(vertical, limit=limit)
    else:
        startups = db.get_all_startups()
        startups = startups[offset : offset + limit]

    return [StartupResponse(**s) for s in startups]


@router.get("/verticals", response_model=VerticalsResponse)
async def get_verticals(
    db: Database = Depends(get_database),
    category_mapper: CategoryMapper = Depends(get_category_mapper),
):
    """Get all climate verticals with startup counts."""
    # Get base vertical info
    all_verticals = category_mapper.get_all_verticals()

    # Get counts from database
    stats = db.get_stats()
    vertical_counts = stats.get("verticals", {})

    # Combine
    verticals = []
    for v in all_verticals:
        verticals.append(
            VerticalInfo(
                id=v["id"],
                name=v["name"],
                description=v.get("description"),
                startup_count=vertical_counts.get(v["id"], 0),
            )
        )

    # Sort by count descending
    verticals.sort(key=lambda x: x.startup_count, reverse=True)

    return VerticalsResponse(
        verticals=verticals,
        total_verticals=len(verticals),
    )
