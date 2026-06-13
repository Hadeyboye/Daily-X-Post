"""
agents package

All specialist agents for the daily_x_posts autonomous CMO.

Each agent is a pure function (or thin class) that:
- Accepts the current AgentState
- Mutates / returns an updated AgentState (immutable-friendly)
- Uses injected tools + memory + LLM client
- Logs every important decision to the state audit trail

This design keeps the graph clean and the agents independently testable.
"""

from .research import research_node
from .strategist import strategist_node
from .creator import creator_node
from .optimizer import optimizer_node
from .analyst import analyst_node
from .executor import executor_node
from .supervisor import supervisor_node, should_continue

__all__ = [
    "research_node",
    "strategist_node",
    "creator_node",
    "optimizer_node",
    "analyst_node",
    "executor_node",
    "supervisor_node",
    "should_continue",
]
