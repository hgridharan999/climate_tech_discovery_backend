"""Pydantic models for API request/response schemas."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class StartupBase(BaseModel):
    """Base startup schema."""

    id: int
    name: str
    short_description: Optional[str] = None
    long_description: Optional[str] = None
    founded_year: Optional[int] = None
    total_funding_usd: Optional[float] = None
    funding_stage: Optional[str] = None
    employee_count: Optional[str] = None
    website_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    headquarters_location: Optional[str] = None
    country: Optional[str] = None
    primary_vertical: Optional[str] = None
    secondary_verticals: Optional[List[str]] = None
    technologies: Optional[List[str]] = None
    keywords: Optional[List[str]] = None


class StartupResponse(StartupBase):
    """Startup response schema with additional metadata."""

    source: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SearchRequest(BaseModel):
    """Search request schema."""

    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    top_k: int = Field(default=20, ge=1, le=100, description="Number of results")
    vertical_filter: Optional[str] = Field(
        default=None, description="Filter by climate vertical"
    )
    founded_year_min: Optional[int] = Field(
        default=None, ge=1990, le=2030, description="Minimum founded year"
    )
    founded_year_max: Optional[int] = Field(
        default=None, ge=1990, le=2030, description="Maximum founded year"
    )
    min_funding_usd: Optional[float] = Field(
        default=None, ge=0, description="Minimum funding amount in USD"
    )
    enable_diversity: bool = Field(
        default=True, description="Enable result diversification"
    )
    enable_query_expansion: bool = Field(
        default=True, description="Enable query expansion with synonyms"
    )


class SearchResultItem(BaseModel):
    """Individual search result."""

    startup: StartupResponse
    score: float = Field(..., description="Relevance score")


class SearchResponse(BaseModel):
    """Search response schema."""

    query: str
    expanded_query: Optional[str] = None
    total_results: int
    results: List[SearchResultItem]
    filters_applied: Dict[str, Any]
    processing_time_ms: float


class VerticalInfo(BaseModel):
    """Climate vertical information."""

    id: str
    name: str
    description: Optional[str] = None
    startup_count: int = 0


class VerticalsResponse(BaseModel):
    """Response with all verticals."""

    verticals: List[VerticalInfo]
    total_verticals: int


class StatsResponse(BaseModel):
    """Database statistics response."""

    total_startups: int
    verticals: Dict[str, int]
    total_funding: float
    avg_funding: float
    max_funding: float
    min_year: Optional[int]
    max_year: Optional[int]
    last_updated: str


class InteractionLogRequest(BaseModel):
    """Request to log user interaction."""

    query: str = Field(..., description="Search query")
    startup_id: int = Field(..., description="Clicked startup ID")
    rank: int = Field(..., ge=1, description="Position in search results")
    action: str = Field(default="click", description="Interaction type")
    session_id: Optional[str] = Field(default=None, description="Session identifier")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    database_connected: bool
    search_initialized: bool
    startup_count: int


class EvaluationResult(BaseModel):
    """Search evaluation result."""

    query: str
    expected_vertical: Optional[str]
    top_results: List[str]
    top_verticals: List[str]
    metrics: Dict[str, float]


class EvaluationResponse(BaseModel):
    """Evaluation response with aggregate metrics."""

    total_queries: int
    aggregate_metrics: Dict[str, float]
    query_results: List[EvaluationResult]
