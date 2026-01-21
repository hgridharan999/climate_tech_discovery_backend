"""FAISS vector search index manager."""

import logging
from pathlib import Path
from typing import List, Tuple, Optional

import numpy as np

from ..core.config import settings

logger = logging.getLogger(__name__)


class FaissManager:
    """Manages FAISS index for vector similarity search."""

    def __init__(self, embedding_dim: int = None):
        self.embedding_dim = embedding_dim or settings.embedding_dim
        self.index = None
        self.startup_ids: List[int] = []

    def build_index(self, embeddings: np.ndarray, startup_ids: List[int]):
        """
        Build FAISS index from embeddings.
        Uses IndexFlatIP for exact cosine similarity (embeddings are normalized).
        """
        try:
            import faiss
        except ImportError:
            logger.error("FAISS not installed. Install with: pip install faiss-cpu")
            raise

        if len(embeddings) == 0:
            logger.warning("No embeddings provided")
            return

        # Ensure embeddings are float32
        embeddings = embeddings.astype(np.float32)

        # Create inner product index (equivalent to cosine similarity for normalized vectors)
        self.embedding_dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(self.embedding_dim)

        # Add vectors to index
        self.index.add(embeddings)
        self.startup_ids = list(startup_ids)

        logger.info(
            f"Built FAISS index with {self.index.ntotal} vectors, dim={self.embedding_dim}"
        )

    def search(
        self, query_embedding: np.ndarray, top_k: int = 20
    ) -> List[Tuple[int, float]]:
        """
        Search for similar vectors.

        Returns:
            List of (startup_id, similarity_score) tuples
        """
        if self.index is None or self.index.ntotal == 0:
            logger.warning("FAISS index not initialized or empty")
            return []

        # Ensure query is 2D and float32
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)
        query_embedding = query_embedding.astype(np.float32)

        # Search
        k = min(top_k, self.index.ntotal)
        distances, indices = self.index.search(query_embedding, k)

        # Map indices to startup IDs
        results = []
        for idx, score in zip(indices[0], distances[0]):
            if 0 <= idx < len(self.startup_ids):
                results.append((self.startup_ids[idx], float(score)))

        return results

    def save_index(self, index_path: str = None):
        """Save FAISS index to file."""
        try:
            import faiss
        except ImportError:
            raise

        if self.index is None:
            logger.warning("No index to save")
            return

        index_path = Path(index_path or settings.faiss_index_path)
        index_path.parent.mkdir(parents=True, exist_ok=True)

        faiss.write_index(self.index, str(index_path))
        logger.info(f"Saved FAISS index to {index_path}")

    def load_index(self, index_path: str = None, startup_ids: List[int] = None):
        """Load FAISS index from file."""
        try:
            import faiss
        except ImportError:
            raise

        index_path = Path(index_path or settings.faiss_index_path)

        if not index_path.exists():
            logger.warning(f"FAISS index file not found: {index_path}")
            return False

        self.index = faiss.read_index(str(index_path))
        self.embedding_dim = self.index.d

        if startup_ids:
            self.startup_ids = list(startup_ids)

        logger.info(
            f"Loaded FAISS index with {self.index.ntotal} vectors from {index_path}"
        )
        return True

    def get_stats(self) -> dict:
        """Get index statistics."""
        if self.index is None:
            return {"initialized": False}

        return {
            "initialized": True,
            "total_vectors": self.index.ntotal,
            "embedding_dim": self.embedding_dim,
            "startup_ids_count": len(self.startup_ids),
        }
