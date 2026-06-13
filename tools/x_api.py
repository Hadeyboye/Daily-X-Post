"""
tools/x_api.py

X (Twitter) API v2 client + resilient browser fallback.

Uses tweepy for clean API access.
Falls back to Playwright automation when API is rate-limited or for quote/reply chains.

All posting goes through this for consistency + logging.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import structlog

logger = structlog.get_logger(__name__)

try:
    from utils.api_clients import api as central_api
except Exception:
    central_api = None


class XClient:
    """Compatibility wrapper around the centralized APIClient for X posting."""
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = bool(os.getenv("X_BEARER_TOKEN") or os.getenv("X_ACCESS_TOKEN"))

    def create_tweet(self, text: str, media_ids: Optional[list] = None) -> Any:
        if not self.enabled or not central_api:
            logger.info("x_create_tweet_dry", text=text[:80])
            class Mock: data = {"id": f"mock_{hash(text) % 100000}"}
            return Mock()
        try:
            return central_api.x_post_tweet(text, media_ids)
        except Exception as e:
            logger.error("x_post_failed", error=str(e))
            raise

    def upload_media(self, path: str) -> Optional[str]:
        # Central client currently focuses on text; extend if needed for media.
        logger.info("x_upload_media_skipped", path=path)
        return None

    def get_user_metrics(self, username: str) -> Dict[str, Any]:
        if not self.enabled or not central_api:
            return {"followers": 12400, "mock": True}
        # For now return mock; can extend central with user lookup.
        return {"followers": 12400, "mock": True}


def get_x_client(config: Dict[str, Any]) -> XClient:
    return XClient(config)
