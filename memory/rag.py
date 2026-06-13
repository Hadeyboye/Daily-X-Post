"""
memory/rag.py

Lightweight RAG orchestration helpers.

For v1 we do retrieval inside the agents directly against the VectorStore.
This file provides higher-level "memory packs" that can be injected into prompts.

Future: GraphRAG, entity memory, user-uploaded brand bible, etc.
"""

from __future__ import annotations

from typing import Any, Dict, List


def build_rag_context(
    vector_store: Any,
    query: str,
    history_store: Any,
    k: int = 5,
) -> str:
    """Assemble a compact, high-signal context block for prompt injection."""
    vector_hits = vector_store.similarity_search(query, k=k)
    past_posts = history_store.get_recent_high_performers(limit=3) if history_store else []

    context_parts = ["=== HIGH-SIGNAL PAST CONTENT ==="]
    for hit in vector_hits:
        context_parts.append(f"- {hit.page_content[:210]}")

    if past_posts:
        context_parts.append("\n=== RECENT WINNING POSTS ===")
        for p in past_posts:
            context_parts.append(f"- {str(p.get('text', ''))[:160]}")

    return "\n".join(context_parts)
