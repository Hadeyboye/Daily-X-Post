"""
agents/supervisor.py

Supervisor Agent — the meta-reasoning orchestrator.

This is the single most important piece of the architecture.

It:
- Decides which specialist to call next (conditional routing)
- Maintains global strategy and iteration budget
- Handles escalation to human
- Triggers self-improvement experiments
- Aggregates parallel research results
- Enforces safety + budget + approval policies
- Can pause the graph for human-in-the-loop
"""

from __future__ import annotations

from typing import Any, Dict, Literal

import structlog

from graph.state import AgentState

logger = structlog.get_logger(__name__)


def supervisor_node(
    state: AgentState,
    config: Dict[str, Any],
    vector_store: Any,
    history_store: Any,
    safety: Any,
) -> AgentState:
    """
    The supervisor is deliberately lightweight. It mostly reads state and sets next_action.
    Real intelligence lives in the conditional edge function + specialist nodes.
    """
    state.current_agent = "supervisor"  # type: ignore[assignment]
    state.iteration += 1
    state.add_audit("supervisor", "reasoning_step", {"iteration": state.iteration})

    sup_cfg = config.get("supervisor", {})
    max_iter = state.max_iterations or sup_cfg.get("max_iterations", 12)

    # Safety escalation
    if safety and any(d.safety_score < 0.4 for d in state.content_drafts):
        state.escalation_reason = "low_safety_score"
        state.next_action = "escalate"
        state.add_audit("supervisor", "escalated", {"reason": state.escalation_reason})
        return state

    # Human gate
    if state.requires_approval and len(state.content_drafts) > 0 and not state.approval_gate_passed:
        state.next_action = "executor"  # Executor will respect the gate
        return state

    # Budget / iteration control
    if state.iteration >= max_iter:
        state.next_action = "end"
        state.completed_at = state.completed_at or __import__("datetime").datetime.utcnow()
        return state

    # Default intelligent routing (very simple finite state machine + priority)
    if not state.research_signals:
        state.next_action = "research"
    elif not state.content_calendar:
        state.next_action = "strategist"
    elif not state.content_drafts:
        state.next_action = "creator"
    elif state.predicted_virality < 0.55 or len(state.rl_feedback) < 3:
        state.next_action = "optimizer"
    elif len(state.published_posts) == 0:
        state.next_action = "executor"
    elif not state.roi_summary:
        state.next_action = "analyst"
    else:
        # Self-improvement trigger
        if state.trigger == "self_improve" or state.iteration % 3 == 0:
            state.next_action = "research"
        else:
            state.next_action = "end"

    state.add_audit("supervisor", "routed", {"next": state.next_action, "iteration": state.iteration})
    return state


def should_continue(state: AgentState, config: Dict[str, Any]) -> str:
    """
    Conditional edge function. This is where the real supervisor decision lives.
    Returns the name of the next node or special tokens ("end", "escalate").
    """
    next_action = state.next_action or "end"

    if next_action == "escalate":
        return "escalate"
    if next_action in {"end", "finish"} or state.iteration >= state.max_iterations:
        return "end"

    # Map action to actual node name
    mapping = {
        "research": "research",
        "strategist": "strategist",
        "creator": "creator",
        "optimizer": "optimizer",
        "analyst": "analyst",
        "executor": "executor",
    }
    return mapping.get(next_action, "end")
