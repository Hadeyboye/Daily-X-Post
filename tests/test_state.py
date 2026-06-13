"""
tests/test_state.py

Basic smoke tests for the core AgentState model.
"""

import pytest
from graph.state import AgentState, ContentDraft, PostFormat, create_initial_state


def test_state_creation():
    state = create_initial_state({"brand": {"name": "Test"}, "niche": {}})
    assert state.run_id.startswith("run_")
    assert state.iteration == 0
    assert state.brand["name"] == "Test"


def test_draft_model():
    draft = ContentDraft(
        format=PostFormat.THREAD,
        text="Hook tweet here",
        thread_parts=["1/ Hook", "2/ Body"],
        predicted_virality=0.78,
    )
    assert draft.format == PostFormat.THREAD
    assert len(draft.thread_parts) == 2


def test_state_audit():
    state = AgentState()
    state.add_audit("test", "action", {"key": "value"})
    assert len(state.audit_trail) == 1
    assert state.audit_trail[0]["agent"] == "test"
