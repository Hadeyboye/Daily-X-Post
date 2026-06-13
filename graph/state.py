"""
graph/state.py

Central typed state for the entire daily_x_posts multi-agent system.
Uses Pydantic v2 for strong validation, serialization, and defaults.

This state is passed through every node of the LangGraph.
It is checkpointed (enables human-in-the-loop, time travel, recovery).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class PostFormat(str, Enum):
    THREAD = "thread"
    SINGLE = "single"
    CAROUSEL = "carousel"
    POLL = "poll"
    VIDEO_SHORT = "video_short"
    MEME = "meme"
    QUOTE = "quote"


class AgentName(str, Enum):
    SUPERVISOR = "supervisor"
    RESEARCH = "research"
    STRATEGIST = "strategist"
    CREATOR = "creator"
    OPTIMIZER = "optimizer"
    ANALYST = "analyst"
    EXECUTOR = "executor"


class CampaignGoal(str, Enum):
    AWARENESS = "awareness"
    ENGAGEMENT = "engagement"
    GROWTH = "growth"
    CONVERSION = "conversion"
    AUTHORITY = "authority"


class ContentDraft(BaseModel):
    """A single piece of multimodal content ready (or almost ready) for publishing."""
    id: str = Field(default_factory=lambda: f"draft_{int(datetime.utcnow().timestamp()*1000)}")
    format: PostFormat
    text: str  # Primary text or thread (numbered 1/ 2/ ...)
    thread_parts: List[str] = Field(default_factory=list)
    image_prompts: List[str] = Field(default_factory=list)
    image_paths: List[str] = Field(default_factory=list)  # Local or URLs after generation
    video_prompt: Optional[str] = None
    video_path: Optional[str] = None
    poll: Optional[Dict[str, Any]] = None
    hashtags: List[str] = Field(default_factory=list)
    cta: str = ""
    predicted_virality: float = Field(ge=0.0, le=1.0, default=0.5)
    predicted_engagement: Dict[str, float] = Field(default_factory=dict)
    brand_alignment_score: float = 0.8
    safety_score: float = 1.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    revised: bool = False
    revision_notes: str = ""


class ResearchSignal(BaseModel):
    source: str
    content: str
    score: float = 0.5  # relevance / velocity
    url: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PerformanceMetric(BaseModel):
    post_id: str
    platform: str = "x"
    impressions: int = 0
    engagements: int = 0
    likes: int = 0
    reposts: int = 0
    replies: int = 0
    saves: int = 0
    profile_visits: int = 0
    link_clicks: int = 0
    engagement_rate: float = 0.0
    virality_score: float = 0.0  # internal composite
    collected_at: datetime = Field(default_factory=datetime.utcnow)


class AgentState(BaseModel):
    """
    The single source of truth passed between all agents.

    Everything important lives here:
    - Current campaign context
    - Research corpus
    - Content pipeline (drafts → optimized → approved → published)
    - Metrics & learning signals
    - Memory pointers (vector ids, episode ids)
    - Audit / decision trail for explainability
    - Human feedback
    """

    # --- Identity & Control ---
    run_id: str = Field(default_factory=lambda: f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}")
    trigger: Literal["scheduled", "manual", "daily_research", "self_improve", "experiment"] = "manual"
    current_agent: AgentName = AgentName.SUPERVISOR
    iteration: int = 0
    max_iterations: int = 12

    # --- Context ---
    brand: Dict[str, Any] = Field(default_factory=dict)
    niche: Dict[str, Any] = Field(default_factory=dict)
    config: Dict[str, Any] = Field(default_factory=dict)
    campaign_goal: CampaignGoal = CampaignGoal.ENGAGEMENT
    target_audience: str = "technical builders and AI-curious professionals"

    # --- Research Layer ---
    research_signals: List[ResearchSignal] = Field(default_factory=list)
    competitor_insights: List[str] = Field(default_factory=list)
    sentiment_summary: str = ""
    trend_forecast: List[Dict[str, Any]] = Field(default_factory=list)
    research_insights: str = ""  # Narrative synthesis

    # --- Strategy Layer ---
    content_calendar: List[Dict[str, Any]] = Field(default_factory=list)  # {date, theme, format, goal}
    active_hypotheses: List[str] = Field(default_factory=list)
    persona_insights: Dict[str, Any] = Field(default_factory=dict)

    # --- Creation Layer ---
    content_drafts: List[ContentDraft] = Field(default_factory=list)
    selected_draft_ids: List[str] = Field(default_factory=list)

    # --- Optimization & Learning ---
    predicted_virality: float = 0.0  # Global for this run
    ab_test_variants: List[Dict[str, Any]] = Field(default_factory=list)
    rl_feedback: List[Dict[str, Any]] = Field(default_factory=list)  # Raw engagement deltas

    # --- Execution Layer ---
    scheduled_jobs: List[Dict[str, Any]] = Field(default_factory=list)
    published_posts: List[Dict[str, Any]] = Field(default_factory=list)  # {id, url, draft_id, time}

    # --- Analytics ---
    metrics: List[PerformanceMetric] = Field(default_factory=list)
    roi_summary: Dict[str, Any] = Field(default_factory=dict)
    growth_forecast: Dict[str, Any] = Field(default_factory=dict)

    # --- Memory & RAG pointers ---
    vector_memory_ids: List[str] = Field(default_factory=list)
    episodic_memory: List[str] = Field(default_factory=list)  # Recent successful post ids
    rag_context: str = ""  # Injected context from memory this cycle

    # --- Human-in-the-Loop & Control ---
    requires_approval: bool = True
    human_feedback: List[Dict[str, Any]] = Field(default_factory=list)  # {draft_id, action, notes, score}
    approval_gate_passed: bool = False
    escalation_reason: Optional[str] = None

    # --- Observability & Audit ---
    messages: List[Dict[str, Any]] = Field(default_factory=list)  # LangGraph-style message log
    audit_trail: List[Dict[str, Any]] = Field(default_factory=list)  # Every major decision
    langsmith_run_id: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    # --- Internal flags for routing ---
    next_action: Optional[str] = None  # Used by supervisor conditional edges
    parallel_research_complete: bool = False

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

    @field_validator("content_drafts", mode="before")
    @classmethod
    def ensure_drafts(cls, v: Any) -> List[ContentDraft]:
        if v is None:
            return []
        return [d if isinstance(d, ContentDraft) else ContentDraft.model_validate(d) for d in v]

    def add_audit(self, agent: str, action: str, details: Dict[str, Any]) -> None:
        self.audit_trail.append({
            "timestamp": datetime.utcnow().isoformat(),
            "agent": agent,
            "action": action,
            "details": details,
            "iteration": self.iteration,
        })

    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None) -> None:
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        })

    def get_latest_drafts(self, limit: int = 5) -> List[ContentDraft]:
        return sorted(self.content_drafts, key=lambda d: d.predicted_virality, reverse=True)[:limit]

    def to_summary(self) -> str:
        return (
            f"Run {self.run_id} | Iteration {self.iteration} | "
            f"Drafts: {len(self.content_drafts)} | "
            f"Published: {len(self.published_posts)} | "
            f"Pred. Virality: {self.predicted_virality:.2f}"
        )


def create_initial_state(
    config: Dict[str, Any],
    trigger: str = "manual",
    brand: Optional[Dict[str, Any]] = None,
    niche: Optional[Dict[str, Any]] = None,
) -> AgentState:
    """Factory for a fresh, well-seeded state."""
    return AgentState(
        trigger=trigger,  # type: ignore[arg-type]
        brand=brand or config.get("brand", {}),
        niche=niche or config.get("niche", {}),
        config=config,
        max_iterations=config.get("supervisor", {}).get("max_iterations", 12),
        requires_approval=config.get("executor", {}).get("human_approval", True),
    )
