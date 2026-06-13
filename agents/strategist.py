"""
agents/strategist.py

Strategist Agent — turns research into executable content strategy.

- Dynamic content calendar (next 7-14 days)
- Audience persona refinement
- Theme + format hypotheses (A/B testable)
- Personalization rules per segment
- Goal alignment (awareness / engagement / authority / growth)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

import structlog

from graph.state import AgentState, CampaignGoal

logger = structlog.get_logger(__name__)


def strategist_node(
    state: AgentState,
    config: Dict[str, Any],
    vector_store: Any,
    history_store: Any,
) -> AgentState:
    state.current_agent = "strategist"  # type: ignore
    state.iteration += 1
    state.add_audit("strategist", "start", {})

    cal_cfg = config.get("calendar", {})
    posts_per_day = cal_cfg.get("posts_per_day", 3)
    best_times = cal_cfg.get("best_times", ["08:30", "12:45", "17:15"])
    theme_rotation = cal_cfg.get("theme_rotation", ["deep_dive", "contrarian_take", "tool_tutorial"])

    today = datetime.utcnow().date()
    calendar: List[Dict[str, Any]] = []

    # Build 14-day rolling calendar
    for day_offset in range(14):
        date = today + timedelta(days=day_offset)
        day_name = date.strftime("%A")
        is_rest = day_name in cal_cfg.get("rest_days", ["Sunday"])

        daily_posts = []
        for i in range(posts_per_day if not is_rest else 1):
            theme = theme_rotation[(day_offset + i) % len(theme_rotation)]
            fmt = ["thread", "carousel", "single", "poll"][(day_offset + i) % 4]
            daily_posts.append({
                "time": best_times[i % len(best_times)],
                "theme": theme,
                "format": fmt,
                "goal": "engagement" if i == 0 else "authority",
                "hypothesis": f"Posts about {theme} on {day_name} will outperform baseline by 18-35%",
            })
        calendar.append({
            "date": date.isoformat(),
            "day": day_name,
            "posts": daily_posts,
            "rest_day": is_rest,
        })

    state.content_calendar = calendar

    # Persona refinement (simple RAG-augmented)
    past_wins = history_store.get_recent_high_performers(limit=8) if history_store else []
    persona = {
        "primary": state.target_audience,
        "secondary": "Indie hackers and technical founders",
        "pain_points": ["shipping velocity", "evaluating new AI tools", "separating signal from noise"],
        "content_preferences": ["data-backed threads", "contrarian takes", "actionable playbooks"],
        "from_memory": [p.get("text", "")[:120] for p in past_wins[:3]],
    }
    state.persona_insights = persona

    # Hypotheses for Optimizer
    state.active_hypotheses = [
        "Longer technical threads (8-11 tweets) with 1 strong data point outperform short tips",
        "Carousel images increase save rate 2.1x vs pure text in AI niche",
        "Posting a poll + follow-up thread 90 minutes later increases reply quality",
        "Meme formats work for awareness but hurt authority perception",
    ]

    # Choose today's primary goal
    state.campaign_goal = CampaignGoal.ENGAGEMENT

    state.research_insights += "\n\n[Strategist] Calendar locked for 14 days. 4 testable hypotheses active."
    state.add_audit("strategist", "calendar_built", {"days": 14, "posts_planned": sum(len(d["posts"]) for d in calendar)})
    state.next_action = "creator"
    return state
