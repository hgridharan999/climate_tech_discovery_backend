"""BERT embeddings using sentence-transformers."""

import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

import numpy as np

from ..core.config import settings

logger = logging.getLogger(__name__)


class Embedder:
    """Generates embeddings using sentence-transformers."""

    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.embedding_model
        self.model = None
        self.batch_size = settings.embedding_batch_size
        self.embedding_dim = settings.embedding_dim

    def _load_model(self):
        """Lazy load the embedding model."""
        if self.model is None:
            logger.info(f"Loading embedding model: {self.model_name}")
            try:
                from sentence_transformers import SentenceTransformer

                self.model = SentenceTransformer(self.model_name)
                logger.info("Embedding model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                raise

    def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for a single text."""
        self._load_model()
        embedding = self.model.encode(
            text, normalize_embeddings=True, show_progress_bar=False
        )
        return embedding

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for a batch of texts."""
        self._load_model()

        if not texts:
            return np.array([])

        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=True,
        )
        return embeddings

    def embed_startups(self, startups: List[Dict[str, Any]]) -> np.ndarray:
        """
        Generate embeddings for startups.
        Combines name and description for richer semantic representation.
        """
        texts = []
        for startup in startups:
            # Combine name and description for embedding
            text_parts = [startup.get("name", "")]

            if startup.get("short_description"):
                text_parts.append(startup["short_description"])

            if startup.get("long_description"):
                text_parts.append(startup["long_description"])

            if startup.get("technologies"):
                techs = startup["technologies"]
                if isinstance(techs, list):
                    text_parts.append(" ".join(techs))
                else:
                    text_parts.append(str(techs))

            combined_text = " ".join(text_parts)
            texts.append(combined_text)

        return self.embed_batch(texts)

    def save_embeddings(
        self,
        embeddings: np.ndarray,
        startup_ids: List[int],
        embeddings_path: str = None,
        mapping_path: str = None,
    ):
        """Save embeddings and ID mapping to files."""
        embeddings_path = Path(embeddings_path or settings.embeddings_path)
        mapping_path = Path(mapping_path or settings.id_mapping_path)

        # Create directories
        embeddings_path.parent.mkdir(parents=True, exist_ok=True)
        mapping_path.parent.mkdir(parents=True, exist_ok=True)

        # Save embeddings as numpy file
        np.save(str(embeddings_path), embeddings)
        logger.info(f"Saved {len(embeddings)} embeddings to {embeddings_path}")

        # Save ID mapping
        mapping = {
            "startup_ids": startup_ids,
            "embedding_dim": int(embeddings.shape[1]) if len(embeddings) > 0 else 0,
            "count": len(startup_ids),
        }
        with open(mapping_path, "w") as f:
            json.dump(mapping, f)
        logger.info(f"Saved ID mapping to {mapping_path}")

    def load_embeddings(
        self, embeddings_path: str = None, mapping_path: str = None
    ) -> tuple:
        """Load embeddings and ID mapping from files."""
        embeddings_path = Path(embeddings_path or settings.embeddings_path)
        mapping_path = Path(mapping_path or settings.id_mapping_path)

        if not embeddings_path.exists() or not mapping_path.exists():
            logger.warning("Embeddings or mapping file not found")
            return None, None

        embeddings = np.load(str(embeddings_path))
        logger.info(f"Loaded {len(embeddings)} embeddings from {embeddings_path}")

        with open(mapping_path, "r") as f:
            mapping = json.load(f)

        return embeddings, mapping.get("startup_ids", [])

    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings."""
        self._load_model()
        return self.model.get_sentence_embedding_dimension()
