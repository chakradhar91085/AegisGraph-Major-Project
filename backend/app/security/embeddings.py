import logging
from typing import List, Optional
from app.core.config import settings
import numpy as np

logger = logging.getLogger(__name__)

class EmbeddingProvider:
    def __init__(self):
        self.model_name = settings.SECURITY_EMBEDDING_MODEL
        self._model = None

    def _load_model(self):
        if self._model is None:
            logger.info(f"Loading local embedding model: {self.model_name}")
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
                logger.info(f"Successfully loaded {self.model_name}. Dimension: {self._model.get_embedding_dimension()}")
            except ImportError:
                logger.error("sentence-transformers package is not installed. Please install it to use the semantic drift signal.")
                raise
            except Exception as e:
                logger.error(f"Failed to load embedding model {self.model_name}: {e}")
                raise

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Fetches the embedding for a given text using the local sentence-transformers model.
        Normalizes it (L2 norm) so that dot product equals cosine similarity.
        This runs in the same thread but sentence-transformers CPU inference is fast enough
        for the single query scale in Phase 4A development.
        """
        try:
            if self._model is None:
                self._load_model()
                
            # SentenceTransformer returns numpy array
            embedding = self._model.encode(text)
            
            # L2 Normalize
            norm = np.linalg.norm(embedding)
            if norm == 0:
                return embedding.tolist()
            
            normalized = embedding / norm
            return normalized.tolist()
                
        except Exception as e:
            logger.error(f"Failed to fetch embedding: {e}")
            return None

# Singleton
embedding_provider = EmbeddingProvider()
