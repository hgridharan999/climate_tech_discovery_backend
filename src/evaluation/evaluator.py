"""Search evaluation framework with NDCG and other metrics."""

import logging
import math
from typing import List, Dict, Any, Optional
from collections import defaultdict

from ..core.config import settings
from ..search.hybrid_search import HybridSearch

logger = logging.getLogger(__name__)


class SearchEvaluator:
    """Evaluates search quality using standard IR metrics."""

    def __init__(self, search_engine: HybridSearch):
        self.search_engine = search_engine
        self.test_queries = settings.get_test_queries().get("test_queries", [])
        self.config = settings.get_test_queries().get("evaluation_config", {})

    def _dcg(self, relevances: List[float], k: int = 10) -> float:
        """Calculate Discounted Cumulative Gain."""
        dcg = 0.0
        for i, rel in enumerate(relevances[:k]):
            dcg += rel / math.log2(i + 2)  # i+2 because log2(1) = 0
        return dcg

    def _ndcg(self, relevances: List[float], k: int = 10) -> float:
        """Calculate Normalized DCG."""
        dcg = self._dcg(relevances, k)

        # Ideal DCG (perfect ranking)
        ideal_relevances = sorted(relevances, reverse=True)
        idcg = self._dcg(ideal_relevances, k)

        if idcg == 0:
            return 0.0
        return dcg / idcg

    def _precision_at_k(self, relevances: List[float], k: int = 5) -> float:
        """Calculate Precision@K."""
        relevant = sum(1 for r in relevances[:k] if r > 0)
        return relevant / k

    def _recall_at_k(
        self, relevances: List[float], total_relevant: int, k: int = 10
    ) -> float:
        """Calculate Recall@K."""
        if total_relevant == 0:
            return 0.0
        relevant_found = sum(1 for r in relevances[:k] if r > 0)
        return relevant_found / total_relevant

    def _mrr(self, relevances: List[float]) -> float:
        """Calculate Mean Reciprocal Rank."""
        for i, rel in enumerate(relevances):
            if rel > 0:
                return 1.0 / (i + 1)
        return 0.0

    def _calculate_relevance(
        self, result: Dict[str, Any], expected_vertical: str = None
    ) -> float:
        """
        Calculate relevance score for a result.

        Uses vertical matching as a proxy for relevance when we don't have
        explicit relevance judgments.
        """
        startup = result.get("startup", {})

        # If vertical matches expected, consider it relevant
        if expected_vertical:
            if startup.get("primary_vertical") == expected_vertical:
                return 1.0
            secondary = startup.get("secondary_verticals", []) or []
            if expected_vertical in secondary:
                return 0.5

        # Use search score as a weak relevance signal
        score = result.get("score", 0)
        if score > 0.1:
            return 0.5
        return 0.0

    def evaluate_query(
        self, query: str, expected_vertical: str = None
    ) -> Dict[str, Any]:
        """Evaluate a single query."""
        # Run search
        results = self.search_engine.search(
            query=query,
            top_k=20,
            enable_diversity=False,  # Disable for evaluation
        )

        search_results = results.get("results", [])

        # Calculate relevances
        relevances = [
            self._calculate_relevance(r, expected_vertical) for r in search_results
        ]

        # If we have expected vertical, count matching results as total relevant
        if expected_vertical:
            total_relevant = sum(1 for r in relevances if r > 0)
        else:
            total_relevant = 10  # Assume 10 relevant for recall calculation

        # Calculate metrics
        metrics = {
            "ndcg@10": self._ndcg(relevances, k=10),
            "precision@5": self._precision_at_k(relevances, k=5),
            "recall@10": self._recall_at_k(relevances, total_relevant, k=10),
            "mrr": self._mrr(relevances),
            "processing_time_ms": results.get("processing_time_ms", 0),
        }

        # Get top result names and verticals
        top_results = [r["startup"]["name"] for r in search_results[:5]]
        top_verticals = [
            r["startup"].get("primary_vertical", "unknown") for r in search_results[:5]
        ]

        return {
            "query": query,
            "expected_vertical": expected_vertical,
            "top_results": top_results,
            "top_verticals": top_verticals,
            "metrics": metrics,
        }

    def evaluate_test_queries(self) -> Dict[str, Any]:
        """Evaluate all test queries and compute aggregate metrics."""
        if not self.test_queries:
            logger.warning("No test queries configured")
            return {
                "total_queries": 0,
                "aggregate_metrics": {},
                "query_results": [],
            }

        query_results = []
        all_metrics: Dict[str, List[float]] = defaultdict(list)

        for test_query in self.test_queries:
            query = test_query.get("query", "")
            expected_vertical = test_query.get("expected_vertical")

            if not query:
                continue

            try:
                result = self.evaluate_query(query, expected_vertical)
                query_results.append(result)

                # Accumulate metrics
                for metric_name, value in result["metrics"].items():
                    all_metrics[metric_name].append(value)

            except Exception as e:
                logger.error(f"Error evaluating query '{query}': {e}")
                continue

        # Calculate aggregate metrics
        aggregate_metrics = {}
        for metric_name, values in all_metrics.items():
            if values:
                aggregate_metrics[f"mean_{metric_name}"] = sum(values) / len(values)
                aggregate_metrics[f"min_{metric_name}"] = min(values)
                aggregate_metrics[f"max_{metric_name}"] = max(values)

        return {
            "total_queries": len(query_results),
            "aggregate_metrics": aggregate_metrics,
            "query_results": query_results,
        }

    def get_vertical_accuracy(self) -> Dict[str, float]:
        """Calculate accuracy of vertical predictions."""
        if not self.test_queries:
            return {}

        correct = 0
        total = 0

        for test_query in self.test_queries:
            query = test_query.get("query", "")
            expected_vertical = test_query.get("expected_vertical")

            if not query or not expected_vertical:
                continue

            results = self.search_engine.search(query=query, top_k=5)
            search_results = results.get("results", [])

            if search_results:
                top_vertical = search_results[0]["startup"].get("primary_vertical")
                if top_vertical == expected_vertical:
                    correct += 1
            total += 1

        if total == 0:
            return {"accuracy": 0.0, "total": 0, "correct": 0}

        return {
            "accuracy": correct / total,
            "total": total,
            "correct": correct,
        }
