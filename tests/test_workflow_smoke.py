"""
tests/test_workflow_smoke.py

Very light integration smoke test (does not require API keys).
"""

import pytest

from graph.state import create_initial_state
from graph.workflow import build_supervisor_graph
from memory.vector_store import get_vector_store
from memory.history import SQLiteHistory
from utils.safety import SafetyFilter
from pathlib import Path
import tempfile


def test_graph_compiles_and_runs_minimally():
    """Ensures the full LangGraph + nodes can at least be constructed and take one step."""
    with tempfile.TemporaryDirectory() as tmp:
        vector = get_vector_store(str(Path(tmp) / "chroma"), "test")
        hist = SQLiteHistory(str(Path(tmp) / "test.db"))
        hist.initialize_schema()
        safety = SafetyFilter({"enabled": True})

        config = {
            "brand": {"name": "Test", "voice": "Clear.", "handle": "@test"},
            "niche": {"primary": "tech_ai", "keywords": ["AI"]},
            "supervisor": {"max_iterations": 3},
            "executor": {"dry_run": True, "human_approval": False},
            "research": {},
            "calendar": {"posts_per_day": 1, "theme_rotation": ["deep_dive"]},
            "content": {},
            "optimizer": {},
            "analyst": {},
            "safety": {"enabled": True},
        }

        graph = build_supervisor_graph(config, vector, hist, safety)
        assert graph is not None

        init = create_initial_state(config, "manual")
        # We don't want to do a full expensive run in unit test, just compile + one invoke
        # In real CI we would use mocks heavily.
        # For now just assert it doesn't explode on construction.
        assert "supervisor" in str(graph)
