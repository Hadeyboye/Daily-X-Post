"""
tests/test_safety.py
"""

from utils.safety import SafetyFilter
from graph.state import ContentDraft, PostFormat


def test_safety_blocklist():
    safety = SafetyFilter({"enabled": True, "blocked_keywords": ["scam", "guaranteed returns"]})
    draft = ContentDraft(format=PostFormat.SINGLE, text="This is a guaranteed returns opportunity")
    assert safety.score_draft(draft) < 0.3


def test_safety_passes_clean():
    safety = SafetyFilter({"enabled": True, "blocked_keywords": ["scam"]})
    draft = ContentDraft(format=PostFormat.THREAD, text="Solid engineering insight on agent loops.")
    assert safety.score_draft(draft) > 0.7
