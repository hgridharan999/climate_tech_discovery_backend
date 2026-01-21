"""Maps startups to climate verticals based on keywords and descriptions."""

import re
import logging
from typing import List, Dict, Optional, Tuple

from ..core.config import settings

logger = logging.getLogger(__name__)


class CategoryMapper:
    """Maps startup descriptions to climate verticals."""

    def __init__(self):
        taxonomy = settings.get_climate_taxonomy()
        self.verticals = {v["id"]: v for v in taxonomy.get("verticals", [])}
        self.synonyms = taxonomy.get("query_synonyms", {})
        self._build_keyword_index()

    def _build_keyword_index(self):
        """Build an inverted index of keywords to verticals."""
        self.keyword_to_vertical: Dict[str, List[str]] = {}

        for vertical_id, vertical in self.verticals.items():
            for keyword in vertical.get("keywords", []):
                keyword_lower = keyword.lower()
                if keyword_lower not in self.keyword_to_vertical:
                    self.keyword_to_vertical[keyword_lower] = []
                self.keyword_to_vertical[keyword_lower].append(vertical_id)

    def map_startup(
        self, name: str, description: str, technologies: List[str] = None
    ) -> Tuple[Optional[str], List[str]]:
        """
        Map a startup to primary and secondary verticals.

        Returns:
            Tuple of (primary_vertical, secondary_verticals)
        """
        # Combine all text for matching
        text = f"{name} {description or ''} {' '.join(technologies or [])}".lower()

        # Count matches per vertical
        vertical_scores: Dict[str, int] = {}

        for keyword, verticals in self.keyword_to_vertical.items():
            # Use word boundary matching for more accurate results
            pattern = r"\b" + re.escape(keyword) + r"\b"
            matches = len(re.findall(pattern, text, re.IGNORECASE))

            if matches > 0:
                for vertical in verticals:
                    vertical_scores[vertical] = (
                        vertical_scores.get(vertical, 0) + matches
                    )

        if not vertical_scores:
            return None, []

        # Sort by score
        sorted_verticals = sorted(
            vertical_scores.items(), key=lambda x: x[1], reverse=True
        )

        primary = sorted_verticals[0][0]
        secondary = [v[0] for v in sorted_verticals[1:4] if v[1] > 0]

        return primary, secondary

    def get_vertical_name(self, vertical_id: str) -> str:
        """Get the display name for a vertical ID."""
        vertical = self.verticals.get(vertical_id, {})
        return vertical.get("name", vertical_id)

    def get_all_verticals(self) -> List[Dict[str, str]]:
        """Get all verticals with their IDs and names."""
        return [
            {"id": vid, "name": v["name"], "description": v.get("description", "")}
            for vid, v in self.verticals.items()
        ]

    def expand_query(self, query: str) -> str:
        """Expand a query with synonyms for better search coverage."""
        expanded_terms = [query]

        # Check for exact synonym matches
        query_lower = query.lower()
        for term, synonyms in self.synonyms.items():
            if term in query_lower:
                expanded_terms.extend(synonyms)

        # Also check if any synonym is in the query
        for term, synonyms in self.synonyms.items():
            for synonym in synonyms:
                if synonym.lower() in query_lower:
                    expanded_terms.append(term)
                    break

        # Remove duplicates while preserving order
        seen = set()
        unique_terms = []
        for term in expanded_terms:
            if term.lower() not in seen:
                seen.add(term.lower())
                unique_terms.append(term)

        return " ".join(unique_terms)

    def extract_keywords(self, text: str) -> List[str]:
        """Extract climate-related keywords from text."""
        text_lower = text.lower()
        found_keywords = []

        for keyword in self.keyword_to_vertical.keys():
            pattern = r"\b" + re.escape(keyword) + r"\b"
            if re.search(pattern, text_lower, re.IGNORECASE):
                found_keywords.append(keyword)

        return found_keywords
