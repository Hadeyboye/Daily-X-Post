"""
memory/vector_store.py

ChromaDB-backed vector memory for daily_x_posts.

Used for:
- Retrieval of past high-performing posts (style + pattern few-shot)
- Audience signal memory
- Long-term brand voice examples
- Research signal deduplication

Simple, production-grade wrapper with sensible defaults.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
import structlog
from chromadb.config import Settings

logger = structlog.get_logger(__name__)


class VectorStore:
    def __init__(self, persist_dir: str, collection_prefix: str = "dailyx"):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        try:
            self.client = chromadb.PersistentClient(
                path=str(self.persist_dir),
                settings=Settings(anonymized_telemetry=False),
            )
            self.collection_name = f"{collection_prefix}_posts_v1"
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as e:
            # Chroma persist dir can get into a bad state (especially after
            # crashes or version upgrades). For a dev/demo app we auto-recover
            # by wiping the local vector db. This is safe because it's just
            # cached research signals and past post embeddings.
            logger.warning("chroma_persist_corrupted", error=str(e), action="wiping_persist_dir")
            import shutil
            shutil.rmtree(self.persist_dir, ignore_errors=True)
            self.persist_dir.mkdir(parents=True, exist_ok=True)

            self.client = chromadb.PersistentClient(
                path=str(self.persist_dir),
                settings=Settings(anonymized_telemetry=False),
            )
            self.collection_name = f"{collection_prefix}_posts_v1"
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )

        logger.info("vector_store_ready", collection=self.collection_name, path=str(self.persist_dir))

    def add_texts(self, texts: List[str], metadatas: Optional[List[Dict]] = None, ids: Optional[List[str]] = None) -> List[str]:
        if not texts:
            return []
        if ids is None:
            ids = [f"doc_{i}_{hash(t) % 10000000}" for i, t in enumerate(texts)]
        if metadatas is None:
            metadatas = [{}] * len(texts)

        self.collection.add(documents=texts, metadatas=metadatas, ids=ids)
        return ids

    def similarity_search(self, query: str, k: int = 6, where: Optional[Dict] = None) -> List[Any]:
        try:
            res = self.collection.query(
                query_texts=[query],
                n_results=min(k, 10),
                where=where,
            )
            # Return simple objects with page_content + metadata (LangChain-like)
            docs = []
            for i, doc in enumerate(res["documents"][0]):
                docs.append(type("Doc", (), {
                    "page_content": doc,
                    "metadata": res["metadatas"][0][i] if res["metadatas"] and res["metadatas"][0] else {},
                })())
            return docs
        except Exception as e:
            logger.warning("chroma_query_failed", error=str(e))
            return []

    def count(self) -> int:
        return self.collection.count()


def get_vector_store(persist_dir: str, collection_prefix: str = "dailyx") -> VectorStore:
    return VectorStore(persist_dir=persist_dir, collection_prefix=collection_prefix)
