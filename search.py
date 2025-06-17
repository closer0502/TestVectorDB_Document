"""Core logic for semantic search against a Qdrant collection.
This file **should not** be executed directly. It exposes a `SearchEngine`
class that can be reused by CLI / FastAPI front-ends.
"""

from __future__ import annotations

import os
from typing import List, Dict, Any

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

DEFAULT_MODEL = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")
DEFAULT_HOST = os.getenv("QDRANT_HOST", "localhost")
DEFAULT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
DEFAULT_COLLECTION = os.getenv("QDRANT_COLLECTION", "documents")


class SearchEngine:
    """Lightweight wrapper around Qdrant similarity search."""

    def __init__(
        self,
        collection: str = DEFAULT_COLLECTION,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        model_name: str = DEFAULT_MODEL,
    ) -> None:
        self.collection = collection
        self.client = QdrantClient(host, port=port)
        self.model = SentenceTransformer(model_name)
        # quick sanity check: raise if collection doesn't exist
        if collection not in [c.name for c in self.client.get_collections().collections]:
            raise ValueError(f"Collection '{collection}' does not exist on Qdrant@{host}:{port}")

    def query(self, text: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Return a list of payload dicts with an added 'score' field."""
        vec = self.model.encode(text).tolist()
        res = self.client.search(
            collection_name=self.collection,
            query_vector=vec,
            limit=limit,
        )
        return [
            {
                **point.payload,  # type: ignore[arg-type]
                "score": point.score,
            }
            for point in res
        ]
