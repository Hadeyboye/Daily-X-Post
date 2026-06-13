"""
ui/components.py

Reusable, beautiful Streamlit components for the daily_x_posts dashboard.
All components are self-contained and return nothing (they render directly).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import plotly.express as px
import streamlit as st

from graph.state import ContentDraft


def render_safety_banner(safety_score: float) -> None:
    if safety_score >= 0.85:
        st.success(f"Safety Score: {safety_score:.0%} — Clean", icon="✅")
    elif safety_score >= 0.6:
        st.warning(f"Safety Score: {safety_score:.0%} — Review recommended", icon="⚠️")
    else:
        st.error(f"Safety Score: {safety_score:.0%} — Blocked or major revision needed", icon="🛑")


def render_post_preview(draft: Any, key_prefix: str = "") -> None:
    """Rich preview card for a single draft (text + images + actions). Works with both Pydantic models and plain dicts (demo mode)."""
    # Support both model and dict (for demo data)
    if hasattr(draft, "model_dump"):
        d = draft.model_dump()
    else:
        d = draft if isinstance(draft, dict) else draft.__dict__

    fmt = d.get("format", "thread")
    if isinstance(fmt, str):
        fmt = fmt.upper()
    else:
        fmt = getattr(fmt, "value", str(fmt)).upper()

    virality = d.get("predicted_virality", 0.7)
    st.markdown(f"**{fmt}** — Predicted Virality: **{virality:.0%}**")

    text = d.get("text", "")
    thread_parts = d.get("thread_parts", [])
    if thread_parts:
        with st.expander("Full Thread", expanded=True):
            for i, part in enumerate(thread_parts, 1):
                st.markdown(f"**{i}/** {part}")
    elif text:
        st.text_area("Post text", text, height=140, key=f"{key_prefix}_text", disabled=True)

    poll = d.get("poll")
    if poll:
        st.write("**Poll:**", poll.get("question"))
        for opt in poll.get("options", []):
            st.write(f"• {opt}")

    # Images / Carousel
    image_paths = d.get("image_paths", []) or []
    if image_paths:
        cols = st.columns(min(len(image_paths), 4))
        for idx, path in enumerate(image_paths):
            p = str(path)
            if p and Path(p).exists():
                cols[idx % len(cols)].image(p, caption=f"Slide {idx+1}", width="stretch")
            else:
                cols[idx % len(cols)].write(f"🖼️ Carousel image {idx+1}")

    if d.get("video_path"):
        st.video(d.get("video_path"))

    safety = d.get("safety_score", 0.9)
    render_safety_banner(safety)

    notes = d.get("revision_notes", "")
    if notes:
        st.caption(f"Revision note: {notes}")


def render_metrics_chart(metrics: List[Dict[str, Any]]) -> None:
    """Beautiful Plotly engagement over time + breakdown."""
    if not metrics:
        st.info("No metrics yet. Run a campaign or wait for data collection.")
        return

    df = []
    for m in metrics:
        df.append({
            "date": m.get("collected_at", "")[:10],
            "engagements": m.get("engagements", 0),
            "impressions": m.get("impressions", 0),
            "saves": m.get("saves", 0),
        })

    import pandas as pd
    pdf = pd.DataFrame(df)

    fig = px.line(pdf, x="date", y=["engagements", "impressions"], title="Engagement & Reach Over Time")
    st.plotly_chart(fig, width="stretch")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Engagements (period)", sum(m.get("engagements", 0) for m in metrics))
    with col2:
        avg_er = sum(m.get("engagement_rate", 0) for m in metrics) / max(1, len(metrics))
        st.metric("Avg Engagement Rate", f"{avg_er:.2f}%")


def render_calendar_table(calendar: List[Dict[str, Any]]) -> None:
    """Clean calendar view."""
    if not calendar:
        st.info("No calendar generated yet.")
        return

    for day in calendar[:7]:  # Show next week
        with st.expander(f"{day['date']} — {day['day']} ({'REST' if day.get('rest_day') else 'ACTIVE'})"):
            for p in day.get("posts", []):
                st.write(f"**{p['time']}** | {p['theme']} | {p['format']} | Goal: {p.get('goal')}")
                st.caption(p.get("hypothesis", ""))


def render_agent_console(state: Dict[str, Any], run_autonomy_fn: Any) -> None:
    """Interactive agent console for power users."""
    st.subheader("Agent Console — Manual Control")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Force Full Campaign Cycle", type="primary"):
            with st.spinner("Running supervisor graph..."):
                result = run_autonomy_fn("manual_console")
            st.success("Cycle complete — see Analytics & Preview tabs")
            st.json(result.get("audit_trail", [])[-3:])

    with col2:
        if st.button("Run Research Only"):
            st.info("Research node would run here (full graph is always preferred).")

    st.divider()
    st.caption("Current run summary")
    st.json({
        "run_id": state.get("run_id"),
        "iteration": state.get("iteration"),
        "drafts": len(state.get("content_drafts", [])),
        "published": len(state.get("published_posts", [])),
        "next_action": state.get("next_action"),
    })
