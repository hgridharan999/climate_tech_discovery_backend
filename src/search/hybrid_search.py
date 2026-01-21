"""Hybrid search combining FAISS semantic search with BM25 keyword search."""

import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from functools import lru_cache
from collections import defaultdict

from ..core.config import settings
from ..core.database import Database
from .embedder import Embedder
from .faiss_manager import FaissManager
from .bm25_engine import BM25Engine
from .query_processor import QueryProcessor
from .diversifier import ResultDiversifier

logger = logging.getLogger(__name__)


class HybridSearch:
    """
    Hybrid search combining semantic (FAISS) and keyword (BM25) search
    using Reciprocal Rank Fusion (RRF).
    """

    def __init__(self, db: Database):
        self.db = db
        self.embedder = Embedder()
        self.faiss_manager = FaissManager()
        self.bm25_engine = BM25Engine()
        self.query_processor = QueryProcessor()
        self.diversifier = ResultDiversifier()

        self.semantic_weight = settings.semantic_weight
        self.is_initialized = False

    def initialize(self):
        """Initialize search indexes from saved files or rebuild."""
        logger.info("Initializing hybrid search...")

        # Try to load existing embeddings and index
        embeddings, startup_ids = self.embedder.load_embeddings()

        if embeddings is not None and startup_ids:
            # Load FAISS index
            loaded = self.faiss_manager.load_index(startup_ids=startup_ids)
            if not loaded:
                # Rebuild FAISS from embeddings
                self.faiss_manager.build_index(embeddings, startup_ids)
                self.faiss_manager.save_index()

            # Build BM25 index from database
            startups = self.db.get_all_startups()
            self.bm25_engine.build_index(startups)

            self.is_initialized = True
            logger.info("Hybrid search initialized from existing indexes")
        else:
            logger.warning("No existing indexes found. Run rebuild_index to create them.")

    def rebuild_index(self):
        """Rebuild all search indexes from scratch."""
        logger.info("Rebuilding search indexes...")
        start_time = time.time()

        # Get all startups from database
        startups = self.db.get_all_startups()
        if not startups:
            logger.warning("No startups in database to index")
            return

        logger.info(f"Indexing {len(startups)} startups...")

        # Generate embeddings
        embeddings = self.embedder.embed_startups(startups)
        startup_ids = [s["id"] for s in startups]

        # Save embeddings
        self.embedder.save_embeddings(embeddings, startup_ids)

        # Build and save FAISS index
        self.faiss_manager.build_index(embeddings, startup_ids)
        self.faiss_manager.save_index()

        # Build BM25 index
        self.bm25_engine.build_index(startups)

        self.is_initialized = True

        elapsed = time.time() - start_time
        logger.info(f"Index rebuild completed in {elapsed:.2f} seconds")

    def _reciprocal_rank_fusion(
        self,
        semantic_results: List[Tuple[int, float]],
        keyword_results: List[Tuple[int, float]],
        k: int = 60,
    ) -> List[Tuple[int, float]]:
        """
        Combine results using Reciprocal Rank Fusion.

        RRF score = sum(1 / (k + rank)) for each ranking list

        Args:
            semantic_results: (startup_id, score) from FAISS
            keyword_results: (startup_id, score) from BM25
            k: RRF constant (default 60, standard value)

        Returns:
            Combined (startup_id, rrf_score) list sorted by score
        """
        rrf_scores: Dict[int, float] = defaultdict(float)

        # Add semantic search contribution (weighted)
        for rank, (startup_id, _) in enumerate(semantic_results):
            rrf_scores[startup_id] += self.semantic_weight / (k + rank + 1)

        # Add keyword search contribution (weighted)
        keyword_weight = 1.0 - self.semantic_weight
        for rank, (startup_id, _) in enumerate(keyword_results):
            rrf_scores[startup_id] += keyword_weight / (k + rank + 1)

        # Sort by RRF score
        sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_results

    def search(
        self,
        query: str,
        top_k: int = None,
        vertical_filter: str = None,
        founded_year_min: int = None,
        founded_year_max: int = None,
        min_funding_usd: float = None,
        enable_diversity: bool = True,
        enable_query_expansion: bool = True,
    ) -> Dict[str, Any]:
        """
        Perform hybrid search.

        Returns:
            Dictionary with query, results, and metadata
        """
        start_time = time.time()
        top_k = top_k or settings.default_top_k

        if not self.is_initialized:
            self.initialize()

        # Clean and process query
        clean_query = self.query_processor.clean_query(query)

        # Extract implicit filters from query
        extracted_filters = self.query_processor.extract_filters(query)
        vertical_filter = vertical_filter or extracted_filters.get("vertical_filter")
        founded_year_min = founded_year_min or extracted_filters.get("founded_year_min")
        founded_year_max = founded_year_max or extracted_filters.get("founded_year_max")
        min_funding_usd = min_funding_usd or extracted_filters.get("min_funding_usd")

        # Expand query for better recall
        search_query = clean_query
        if enable_query_expansion:
            search_query = self.query_processor.expand_query(clean_query)

        # Adjust semantic weight based on query type
        original_weight = self.semantic_weight
        self.semantic_weight = self.query_processor.get_query_vector_weight(clean_query)

        # Get more results than needed for filtering and diversification
        fetch_k = min(top_k * 5, 200)

        # Semantic search using FAISS
        query_embedding = self.embedder.embed_text(search_query)
        semantic_results = self.faiss_manager.search(query_embedding, fetch_k)

        # Keyword search using BM25
        keyword_results = self.bm25_engine.search(search_query, fetch_k)

        # Combine with RRF
        combined_results = self._reciprocal_rank_fusion(semantic_results, keyword_results)

        # Restore original weight
        self.semantic_weight = original_weight

        # Fetch full startup data and apply filters
        results = []
        for startup_id, rrf_score in combined_results:
            startup = self.db.get_startup_by_id(startup_id)
            if not startup:
                continue

            # Apply filters
            if vertical_filter and startup.get("primary_vertical") != vertical_filter:
                continue

            if founded_year_min and (startup.get("founded_year") or 0) < founded_year_min:
                continue

            if founded_year_max and (startup.get("founded_year") or 9999) > founded_year_max:
                continue

            if min_funding_usd and (startup.get("total_funding_usd") or 0) < min_funding_usd:
                continue

            results.append({
                "startup": startup,
                "score": rrf_score,
            })

        # Apply diversification
        if enable_diversity:
            results = self.diversifier.diversify(results, total_results=top_k)
        else:
            results = results[:top_k]

        processing_time = (time.time() - start_time) * 1000

        return {
            "query": query,
            "expanded_query": search_query if enable_query_expansion else None,
            "total_results": len(results),
            "results": results,
            "filters_applied": {
                "vertical": vertical_filter,
                "founded_year_min": founded_year_min,
                "founded_year_max": founded_year_max,
                "min_funding_usd": min_funding_usd,
            },
            "processing_time_ms": round(processing_time, 2),
            "semantic_weight": self.semantic_weight,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get search system statistics."""
        return {
            "is_initialized": self.is_initialized,
            "faiss": self.faiss_manager.get_stats(),
            "bm25": self.bm25_engine.get_stats(),
            "semantic_weight": self.semantic_weight,
        }
