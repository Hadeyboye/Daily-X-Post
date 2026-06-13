"""
graph/workflow.py

LangGraph StateGraph definition for daily_x_posts.

Hybrid architecture:
- Supervisor (conditional router + meta-reasoner)
- Hierarchical: Supervisor owns the high-level plan
- Swarm: Research can fan out in parallel (trends + competitors + web)
- Persistent checkpoints via MemorySaver (easy upgrade to Postgres checkpointer)
- Human-in-the-loop via interrupt_before / interrupt_after on critical nodes

ReAct + tool calling patterns are used inside the individual agent nodes.
"""

from __future__ import annotations

import uuid
from typing import Any, Callable, Dict, List, Literal

import structlog
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from graph.state import AgentState, AgentName
from agents.research import research_node
from agents.strategist import strategist_node
from agents.creator import creator_node
from agents.optimizer import optimizer_node
from agents.analyst import analyst_node
from agents.executor import executor_node
from agents.supervisor import supervisor_node, should_continue

from tools.novita_integration import get_novita_client
from tools.x_api import get_x_client
from utils.safety import SafetyFilter

logger = structlog.get_logger(__name__)


def build_supervisor_graph(
    config: Dict[str, Any],
    vector_store: Any,
    history_store: Any,
    safety: SafetyFilter,
) -> Any:
    """
    Build and compile the full supervisor-orchestrated multi-agent graph.

    Returns a compiled LangGraph app ready for .invoke() / .stream().
    """
    # Shared tool instances (injected into nodes that need them)
    novita = get_novita_client(config)
    x_client = get_x_client(config)

    # Tool node example (for future ReAct-style tool use inside agents)
    # For v1 we keep most tool use inside the agent functions for clarity.
    tools = []  # Extend with @tool decorated functions if desired

    # Create the graph
    workflow = StateGraph(AgentState)

    # Register nodes
    workflow.add_node(AgentName.SUPERVISOR.value, lambda s: supervisor_node(
        s, config=config, vector_store=vector_store, history_store=history_store, safety=safety
    ))
    workflow.add_node(AgentName.RESEARCH.value, lambda s: research_node(
        s, config=config, vector_store=vector_store, novita=novita
    ))
    workflow.add_node(AgentName.STRATEGIST.value, lambda s: strategist_node(
        s, config=config, vector_store=vector_store, history_store=history_store
    ))
    workflow.add_node(AgentName.CREATOR.value, lambda s: creator_node(
        s, config=config, novita=novita, vector_store=vector_store, safety=safety
    ))
    workflow.add_node(AgentName.OPTIMIZER.value, lambda s: optimizer_node(
        s, config=config, vector_store=vector_store, history_store=history_store
    ))
    workflow.add_node(AgentName.ANALYST.value, lambda s: analyst_node(
        s, config=config, history_store=history_store, vector_store=vector_store
    ))
    workflow.add_node(AgentName.EXECUTOR.value, lambda s: executor_node(
        s, config=config, x_client=x_client, history_store=history_store, safety=safety
    ))

    # Optional tool node (example for future expansion)
    if tools:
        workflow.add_node("tools", ToolNode(tools))

    # Entry point
    workflow.set_entry_point(AgentName.SUPERVISOR.value)

    # Supervisor decides routing (the brain)
    workflow.add_conditional_edges(
        AgentName.SUPERVISOR.value,
        lambda state: should_continue(state, config),
        {
            AgentName.RESEARCH.value: AgentName.RESEARCH.value,
            AgentName.STRATEGIST.value: AgentName.STRATEGIST.value,
            AgentName.CREATOR.value: AgentName.CREATOR.value,
            AgentName.OPTIMIZER.value: AgentName.OPTIMIZER.value,
            AgentName.ANALYST.value: AgentName.ANALYST.value,
            AgentName.EXECUTOR.value: AgentName.EXECUTOR.value,
            "end": END,
            "escalate": END,  # Can be extended to a human escalation node
        },
    )

    # After each specialist, always return to supervisor for next decision
    for node in [
        AgentName.RESEARCH.value,
        AgentName.STRATEGIST.value,
        AgentName.CREATOR.value,
        AgentName.OPTIMIZER.value,
        AgentName.ANALYST.value,
        AgentName.EXECUTOR.value,
    ]:
        workflow.add_edge(node, AgentName.SUPERVISOR.value)

    # Compile with checkpointing (critical for HITL + recovery)
    checkpointer = MemorySaver()
    compiled = workflow.compile(checkpointer=checkpointer)

    logger.info(
        "langgraph_supervisor_compiled",
        nodes=list(workflow.nodes.keys()),
        checkpointer="MemorySaver",
    )
    return compiled


def run_workflow(
    graph: Any,
    initial_state: AgentState,
    config: Dict[str, Any],
    thread_id: str | None = None,
) -> Dict[str, Any]:
    """
    Convenience runner that handles checkpointing, recursion limit, and final state extraction.

    Returns the final state as plain dict (easy for UI + persistence).
    """
    thread_id = thread_id or f"thread_{uuid.uuid4().hex[:12]}"
    config_run = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": config.get("supervisor", {}).get("max_iterations", 12) + 5,
    }

    logger.info("workflow_invoking", run_id=initial_state.run_id, thread_id=thread_id)

    # We stream for better observability (can be surfaced in Agent Console)
    final_state = None
    for event in graph.stream(initial_state.model_dump(), config=config_run, stream_mode="values"):
        # event is the latest state snapshot
        final_state = event
        # Optional: surface progress to UI via callback in future

    if final_state is None:
        # Fallback to invoke
        final_state = graph.invoke(initial_state.model_dump(), config=config_run)

    # Mark completion
    if isinstance(final_state, dict):
        final_state["completed_at"] = initial_state.completed_at or None
    else:
        final_state = final_state.model_dump()

    logger.info("workflow_completed", run_id=initial_state.run_id, thread_id=thread_id)
    return final_state
