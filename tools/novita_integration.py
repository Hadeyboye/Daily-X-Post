"""
tools/novita_integration.py

STUB: Novita AI has been completely removed per requirements.
All content generation now uses ONLY Grok Advanced Thinking (local, no LLM calls).
This file remains for import compatibility but does nothing.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


class NovitaClient:
    """Stub - all methods now redirect to Grok Deep Thinking or raise."""
    def __init__(self, *args, **kwargs):
        self.enabled = False
        logger.info("novita_removed_using_grok_deep_thinking")

    def chat_completion(self, *args, **kwargs):
        logger.info("novita_chat_blocked_fallback_to_grok")
        raise NotImplementedError("Novita removed. Grok Deep Thinking is the only generation engine.")

    def generate_image(self, *args, **kwargs):
        logger.info("novita_image_blocked_fallback_to_grok")
        raise NotImplementedError("Novita removed. Use Grok image prompts + placeholders.")

    def generate_video(self, *args, **kwargs):
        raise NotImplementedError("Novita removed.")

def get_novita_client(config: Dict[str, Any]) -> NovitaClient:
    logger.warning("get_novita_client_called_but_novita_removed")
    return NovitaClient()
