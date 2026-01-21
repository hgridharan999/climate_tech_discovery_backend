"""Result diversification to ensure variety in search results."""

import logging
from typing import List, Dict, Any
from collections import defaultdict

from ..core.config import settings

logger = logging.getLogger(__name__)


class ResultDiversifier:
    """Diversifies search results to avoid concentration in single verticals."""

    def __init__(self, max_per_vertical: int = None):
        self.max_per_vertical = max_per_vertical or settings.max_results_per_vertical

    def diversify(
        self,
        results: List[Dict[str, Any]],
        total_results: int = None,
        max_per_vertical: int = None,
    ) -> List[Dict[str, Any]]:
        """
        Diversify results by limiting items per vertical.

        Uses a round-robin approach to interleave results from different verticals
        while respecting the original ranking within each vertical.

        Args:
            results: List of search results with 'startup' containing 'primary_vertical'
            total_results: Maximum total results to return
            max_per_vertical: Maximum results per vertical

        Returns:
            Diversified list of results
        """
        if not results:
            return results

        max_per = max_per_vertical or self.max_per_vertical
        total = total_results or len(results)

        # Group results by vertical
        by_vertical: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        no_vertical: List[Dict[str, Any]] = []

        for result in results:
            startup = result.get("startup", {})
            vertical = startup.get("primary_vertical")

            if vertical:
                by_vertical[vertical].append(result)
            else:
                no_vertical.append(result)

        # Round-robin selection from each vertical
        diversified = []
        vertical_counts: Dict[str, int] = defaultdict(int)

        # First pass: interleave results from different verticals
        round_num = 0
        while len(diversified) < total:
            added_this_round = False

            for vertical in list(by_vertical.keys()):
                if vertical_counts[vertical] >= max_per:
                    continue

                vertical_results = by_vertical[vertical]
                if vertical_counts[vertical] < len(vertical_results):
                    result = vertical_results[vertical_counts[vertical]]
                    diversified.append(result)
                    vertical_counts[vertical] += 1
                    added_this_round = True

                    if len(diversified) >= total:
                        break

            # Add items without vertical
            if no_vertical and len(diversified) < total:
                if round_num < len(no_vertical):
                    diversified.append(no_vertical[round_num])
                    added_this_round = True

            if not added_this_round:
                break

            round_num += 1

        # If we still need more results, add remaining high-scoring ones
        if len(diversified) < total:
            used_ids = {
                r.get("startup", {}).get("id") for r in diversified
            }

            for result in results:
                if len(diversified) >= total:
                    break

                startup_id = result.get("startup", {}).get("id")
                if startup_id not in used_ids:
                    diversified.append(result)
                    used_ids.add(startup_id)

        return diversified[:total]

    def get_vertical_distribution(
        self, results: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Get the distribution of verticals in results."""
        distribution: Dict[str, int] = defaultdict(int)

        for result in results:
            startup = result.get("startup", {})
            vertical = startup.get("primary_vertical", "unknown")
            distribution[vertical] += 1

        return dict(distribution)
