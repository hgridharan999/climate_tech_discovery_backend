"""BM25 keyword search engine."""

import logging
import re
from typing import List, Dict, Any, Tuple

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


class BM25Engine:
    """BM25 keyword search using rank-bm25."""

    def __init__(self):
        self.bm25 = None
        self.startup_ids: List[int] = []
        self.documents: List[List[str]] = []

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization for BM25."""
        if not text:
            return []

        # Lowercase and split on non-alphanumeric characters
        text = text.lower()
        tokens = re.findall(r"\b[a-z0-9]+\b", text)

        # Remove very short tokens and stopwords
        stopwords = {
            "a", "an", "the", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "need", "dare", "ought", "used", "to", "of", "in",
            "for", "on", "with", "at", "by", "from", "as", "into",
            "through", "during", "before", "after", "above", "below",
            "between", "under", "again", "further", "then", "once",
            "and", "but", "or", "nor", "so", "yet", "both", "either",
            "neither", "not", "only", "own", "same", "than", "too",
            "very", "just", "also", "now", "here", "there", "when",
            "where", "why", "how", "all", "each", "every", "both",
            "few", "more", "most", "other", "some", "such", "no",
            "any", "its", "it", "this", "that", "these", "those",
        }

        tokens = [t for t in tokens if len(t) > 1 and t not in stopwords]
        return tokens

    def _prepare_document(self, startup: Dict[str, Any]) -> List[str]:
        """Prepare a startup document for BM25 indexing."""
        text_parts = [
            startup.get("name", ""),
            startup.get("short_description", ""),
            startup.get("long_description", ""),
            startup.get("primary_vertical", ""),
            startup.get("headquarters_location", ""),
        ]

        # Add technologies and keywords
        techs = startup.get("technologies", [])
        if isinstance(techs, list):
            text_parts.extend(techs)
        elif techs:
            text_parts.append(str(techs))

        keywords = startup.get("keywords", [])
        if isinstance(keywords, list):
            text_parts.extend(keywords)
        elif keywords:
            text_parts.append(str(keywords))

        combined_text = " ".join(str(p) for p in text_parts if p)
        return self._tokenize(combined_text)

    def build_index(self, startups: List[Dict[str, Any]]):
        """Build BM25 index from startup documents."""
        self.documents = []
        self.startup_ids = []

        for startup in startups:
            tokens = self._prepare_document(startup)
            if tokens:
                self.documents.append(tokens)
                self.startup_ids.append(startup["id"])

        if self.documents:
            self.bm25 = BM25Okapi(self.documents)
            logger.info(f"Built BM25 index with {len(self.documents)} documents")
        else:
            logger.warning("No documents to index")

    def search(self, query: str, top_k: int = 100) -> List[Tuple[int, float]]:
        """
        Search using BM25.

        Returns:
            List of (startup_id, bm25_score) tuples
        """
        if self.bm25 is None or not self.documents:
            logger.warning("BM25 index not initialized")
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores = self.bm25.get_scores(query_tokens)

        # Get top-k results
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in indexed_scores[:top_k]:
            if score > 0 and idx < len(self.startup_ids):
                results.append((self.startup_ids[idx], float(score)))

        return results

    def get_stats(self) -> dict:
        """Get BM25 index statistics."""
        return {
            "initialized": self.bm25 is not None,
            "document_count": len(self.documents),
            "startup_ids_count": len(self.startup_ids),
        }
