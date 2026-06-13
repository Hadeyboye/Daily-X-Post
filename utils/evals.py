"""
utils/evals.py

Lightweight evaluation harness for the agent system.

Used for:
- Offline prompt / output quality regression tests
- Self-improvement experiment scoring
- CI gating (basic)

In production this would integrate with LangSmith datasets + evaluators.
"""

from __future__ import annotations

from typing import Any, Dict, List

import structlog

logger = structlog.get_logger(__name__)


def evaluate_draft_quality(draft_text: str, brand_voice: str) -> Dict[str, float]:
    """Very cheap heuristic evaluator. Real version uses LLM judge or fine-tuned model."""
    score = 0.6
    if len(draft_text) > 180:
        score += 0.08
    if "?" in draft_text or "you" in draft_text.lower():
        score += 0.07
    if any(word in draft_text.lower() for word in ["data", "study", "shipped", "production"]):
        score += 0.1
    return {
        "overall": min(0.97, round(score, 3)),
        "brand_alignment": 0.78,
        "hook_strength": 0.71,
    }


def run_basic_evals(state: Dict[str, Any]) -> Dict[str, Any]:
    """Run a battery of checks on a finished run state."""
    drafts = state.get("content_drafts", [])
    scores = [evaluate_draft_quality(d.get("text", ""), "")["overall"] for d in drafts]
    return {
        "avg_quality": sum(scores) / max(1, len(scores)) if scores else 0.0,
        "num_drafts": len(drafts),
        "passed_threshold": all(s > 0.6 for s in scores),
    }
