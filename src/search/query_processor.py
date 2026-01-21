"""Query processing and expansion for better search results."""

import re
import logging
from typing import List, Dict, Set

from ..core.config import settings

logger = logging.getLogger(__name__)


class QueryProcessor:
    """Processes and expands search queries for better recall."""

    def __init__(self):
        taxonomy = settings.get_climate_taxonomy()
        self.synonyms = taxonomy.get("query_synonyms", {})
        self.verticals = {v["id"]: v for v in taxonomy.get("verticals", [])}

        # Build reverse synonym map
        self.reverse_synonyms: Dict[str, str] = {}
        for term, synonyms in self.synonyms.items():
            for synonym in synonyms:
                self.reverse_synonyms[synonym.lower()] = term

    def clean_query(self, query: str) -> str:
        """Clean and normalize a query."""
        # Remove extra whitespace
        query = " ".join(query.split())

        # Remove special characters but keep alphanumeric and spaces
        query = re.sub(r"[^\w\s\-]", "", query)

        return query.strip()

    def expand_query(self, query: str) -> str:
        """
        Expand query with synonyms for better recall.
        Returns the original query plus synonym expansions.
        """
        query_lower = query.lower()
        expanded_terms: Set[str] = {query}

        # Check for known synonyms
        for term, synonyms in self.synonyms.items():
            # If the term is in the query, add its synonyms
            if term.lower() in query_lower:
                expanded_terms.update(synonyms)

            # If any synonym is in the query, add the main term
            for synonym in synonyms:
                if synonym.lower() in query_lower:
                    expanded_terms.add(term)

        # Also check for vertical keywords
        for vertical_id, vertical in self.verticals.items():
            for keyword in vertical.get("keywords", []):
                if keyword.lower() in query_lower:
                    # Add other related keywords from the same vertical
                    related = vertical.get("keywords", [])[:3]
                    expanded_terms.update(related)
                    break

        # Remove the original query and add it at the start
        expanded_terms.discard(query)
        result = [query] + list(expanded_terms)

        return " ".join(result)

    def extract_filters(self, query: str) -> Dict[str, any]:
        """
        Extract filter parameters from natural language query.
        E.g., "solar startups in california founded after 2020"
        """
        filters = {}
        query_lower = query.lower()

        # Year patterns
        year_match = re.search(
            r"(?:founded|started|since|after)\s*(?:in\s+)?(\d{4})", query_lower
        )
        if year_match:
            filters["founded_year_min"] = int(year_match.group(1))

        year_before = re.search(r"(?:before|until)\s+(\d{4})", query_lower)
        if year_before:
            filters["founded_year_max"] = int(year_before.group(1))

        # Location patterns
        location_patterns = [
            r"in\s+([a-zA-Z\s]+(?:,\s*[A-Z]{2})?)\s*$",
            r"based\s+in\s+([a-zA-Z\s]+)",
            r"from\s+([a-zA-Z\s]+)",
        ]
        for pattern in location_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                filters["location"] = match.group(1).strip()
                break

        # Funding patterns
        funding_match = re.search(
            r"(?:raised|funding|over)\s*\$?(\d+(?:\.\d+)?)\s*(m|million|b|billion)?",
            query_lower,
        )
        if funding_match:
            amount = float(funding_match.group(1))
            unit = funding_match.group(2) or ""
            if "b" in unit or "billion" in unit:
                amount *= 1_000_000_000
            elif "m" in unit or "million" in unit:
                amount *= 1_000_000
            filters["min_funding_usd"] = amount

        # Vertical detection
        for vertical_id, vertical in self.verticals.items():
            vertical_name = vertical.get("name", "").lower()
            if vertical_name in query_lower:
                filters["vertical_filter"] = vertical_id
                break

            # Check keywords
            for keyword in vertical.get("keywords", []):
                if keyword.lower() in query_lower:
                    filters["vertical_filter"] = vertical_id
                    break

        return filters

    def remove_filter_terms(self, query: str) -> str:
        """Remove filter-related terms from query to get clean search terms."""
        patterns_to_remove = [
            r"(?:founded|started|since|after)\s*(?:in\s+)?\d{4}",
            r"(?:before|until)\s+\d{4}",
            r"in\s+[a-zA-Z\s]+(?:,\s*[A-Z]{2})?\s*$",
            r"based\s+in\s+[a-zA-Z\s]+",
            r"from\s+[a-zA-Z\s]+",
            r"(?:raised|funding|over)\s*\$?\d+(?:\.\d+)?\s*(?:m|million|b|billion)?",
            r"startups?",
            r"companies?",
        ]

        result = query
        for pattern in patterns_to_remove:
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)

        # Clean up extra whitespace
        result = " ".join(result.split())
        return result.strip()

    def get_query_vector_weight(self, query: str) -> float:
        """
        Determine optimal semantic weight based on query characteristics.
        Returns a weight between 0 and 1 for semantic vs keyword search.
        """
        query_lower = query.lower()

        # Conceptual queries benefit more from semantic search
        conceptual_indicators = [
            "like", "similar", "related", "alternative", "comparable",
            "technology for", "solutions for", "companies doing",
            "startups working on", "focused on",
        ]

        # Specific queries benefit more from keyword search
        specific_indicators = [
            "named", "called", "exact", "specifically",
        ]

        for indicator in conceptual_indicators:
            if indicator in query_lower:
                return 0.7  # Higher semantic weight

        for indicator in specific_indicators:
            if indicator in query_lower:
                return 0.4  # Lower semantic weight

        # Default balanced weight
        return 0.6
