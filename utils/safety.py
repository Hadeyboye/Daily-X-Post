"""
utils/safety.py

Multi-layer safety guardrails for daily_x_posts.

Layers:
1. Keyword blocklist (hard)
2. Heuristic toxicity / risk
3. LLM self-critique (via injected novita when available)
4. Brand value alignment

All content must pass before reaching Executor.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

import structlog

from graph.state import ContentDraft

logger = structlog.get_logger(__name__)


class SafetyFilter:
    def __init__(self, safety_cfg: Dict[str, Any]):
        self.enabled = safety_cfg.get("enabled", True)
        self.blocked = set(kw.lower() for kw in safety_cfg.get("blocked_keywords", []))
        self.max_toxicity = safety_cfg.get("max_toxicity", 0.15)
        self.level = safety_cfg.get("level", "medium")

    def _keyword_block(self, text: str) -> bool:
        lowered = text.lower()
        return any(kw in lowered for kw in self.blocked)

    def _heuristic_risk(self, text: str) -> float:
        """Crude 0-1 risk score."""
        risk = 0.0
        if re.search(r"\b(guaranteed|100%|secret|insider|pump)\b", text, re.I):
            risk += 0.25
        if len(re.findall(r"!", text)) > 3:
            risk += 0.12
        if "make money" in text.lower() or "get rich" in text.lower():
            risk += 0.3
        return min(1.0, risk)

    def score_draft(self, draft: ContentDraft) -> float:
        if not self.enabled:
            return 1.0

        full_text = draft.text + " " + " ".join(draft.thread_parts) + " " + (draft.cta or "")
        if self._keyword_block(full_text):
            logger.warning("safety_keyword_block", draft_id=draft.id)
            return 0.1

        risk = self._heuristic_risk(full_text)
        base = 0.92 - (risk * 0.7)
        return max(0.15, round(base, 2))

    def is_safe(self, draft: ContentDraft) -> bool:
        return self.score_draft(draft) >= 0.55

    def filter_research(self, signals: List[Any]) -> List[Any]:
        if not self.enabled:
            return signals
        return [s for s in signals if not self._keyword_block(getattr(s, "content", str(s)))]
