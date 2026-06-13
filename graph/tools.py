"""
graph/tools.py

Shared tools for the agent system.
All tools are designed to be:
- Observable (return rich metadata)
- Resilient (tenacity inside where useful)
- Safe (never execute side effects without explicit permission)

In v1 most heavy lifting happens inside agent nodes.
These are the reusable primitives.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger(__name__)


# --------------------------------------------------------------------------- #
# Research Tools (called by Research Agent)
# --------------------------------------------------------------------------- #

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_x_trends(
    keywords: List[str],
    limit: int = 25,
    mock: bool = False,
) -> List[Dict[str, Any]]:
    """
    Fetch trending topics + posts from X.
    In production this would call X API + semantic search tools.
    """
    if mock:
        return [
            {
                "id": f"mock_trend_{i}",
                "text": f"Exciting development in {kw}: autonomous AI agents are shipping real products",
                "score": 0.92 - (i * 0.03),
                "source": "x_keyword",
                "timestamp": datetime.utcnow().isoformat(),
            }
            for i, kw in enumerate(keywords[:5])
        ]

    # Placeholder for real X API v2 recent search / trends
    logger.info("fetch_x_trends_called", keywords=keywords, limit=limit)
    return [{"id": "real_trend_placeholder", "text": "Real X data would appear here with valid keys", "score": 0.7}]


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1))
def semantic_search_x(
    query: str,
    limit: int = 15,
    mock: bool = False,
) -> List[Dict[str, Any]]:
    """Semantic search over recent X posts (Novita or external embedding + X)."""
    if mock:
        return [
            {"text": f"Semantic hit {i}: {query} is transforming how we build products", "relevance": 0.88}
            for i in range(min(limit, 6))
        ]
    logger.info("semantic_search_x", query=query)
    return []


def analyze_competitor(
    handle: str,
    limit: int = 8,
    mock: bool = False,
) -> List[Dict[str, Any]]:
    """Pull recent posts + engagement from a competitor handle."""
    if mock:
        return [
            {"handle": handle, "text": "Just shipped a new agent framework...", "likes": 1240 + i*50, "reposts": 300}
            for i in range(3)
        ]
    return []


# --------------------------------------------------------------------------- #
# Memory / RAG Tools
# --------------------------------------------------------------------------- #

def retrieve_successful_posts(
    vector_store: Any,
    query: str,
    k: int = 6,
) -> List[Dict[str, Any]]:
    """Retrieve past high-performing content for few-shot / style transfer."""
    try:
        results = vector_store.similarity_search(query, k=k)
        return [{"text": r.page_content, "metadata": r.metadata} for r in results]
    except Exception as e:
        logger.warning("vector_retrieve_failed", error=str(e))
        return []


def store_post_embedding(
    vector_store: Any,
    text: str,
    metadata: Dict[str, Any],
) -> str:
    """Store a post (or draft) into long-term vector memory."""
    doc_id = f"post_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    try:
        vector_store.add_texts([text], metadatas=[metadata], ids=[doc_id])
        return doc_id
    except Exception as e:
        logger.error("vector_store_failed", error=str(e))
        return ""


# --------------------------------------------------------------------------- #
# Analytics Helpers
# --------------------------------------------------------------------------- #

def compute_engagement_rate(metrics: Dict[str, int]) -> float:
    impressions = max(metrics.get("impressions", 1), 1)
    return round((metrics.get("engagements", 0) / impressions) * 100, 2)


def simple_virality_predictor(draft_text: str, past_performance: List[float]) -> float:
    """Extremely lightweight heuristic predictor (upgrade with real model later)."""
    length = len(draft_text)
    has_question = "?" in draft_text
    has_number = any(c.isdigit() for c in draft_text)
    base = 0.55
    if has_question:
        base += 0.08
    if has_number:
        base += 0.06
    if 180 < length < 420:
        base += 0.07
    if past_performance:
        base = 0.6 * base + 0.4 * (sum(past_performance) / len(past_performance))
    return min(0.97, max(0.35, round(base, 3)))


# --------------------------------------------------------------------------- #
# General Purpose
# --------------------------------------------------------------------------- #

def get_current_utc_iso() -> str:
    return datetime.utcnow().isoformat()
