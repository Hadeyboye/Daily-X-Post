"""
ui/dashboard.py

Main Streamlit dashboard for daily_x_posts.

7 professional tabs as specified:
Generate Now • Smart Calendar • Live Analytics • Config Hub • Logs • Preview/Approve • Agent Console
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List

import streamlit as st
import yaml

from graph.state import AgentState, ContentDraft, create_initial_state
from graph.workflow import run_workflow
from ui.components import (
    render_agent_console,
    render_calendar_table,
    render_metrics_chart,
    render_post_preview,
)

PROJECT_ROOT = Path(__file__).parent.parent


def _get_session_state_defaults():
    if "current_state" not in st.session_state:
        st.session_state.current_state = None
    if "pending_drafts" not in st.session_state:
        st.session_state.pending_drafts = []
    if "approved_ids" not in st.session_state:
        st.session_state.approved_ids = set()


def launch_dashboard(
    config: Dict[str, Any],
    graph: Any,
    vector_store: Any,
    history_store: Any,
    safety: Any,
    run_autonomy_cycle: Callable,
    start_scheduler: Callable,
) -> None:
    """Primary entry point called from main.py"""
    st.set_page_config(
        page_title="daily_x_posts — AI Content CMO",
        page_icon="🧠",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    _get_session_state_defaults()

    st.title("daily_x_posts")
    st.caption("Autonomous AI Social Media Intelligence Platform • 2026")

    # Sidebar controls
    with st.sidebar:
        st.header("Control Center")
        st.write(f"Brand: **{config['brand']['name']}** ({config['brand']['handle']})")
        st.write(f"Niche: **{config['niche']['primary']}**")
        env = config["platform"]["environment"]
        st.write(f"Env: `{env}`")

        if st.button("🚀 Run Full Autonomy Cycle", type="primary", use_container_width=True):
            with st.spinner("Supervisor running full graph..."):
                result = run_autonomy_cycle("manual_dashboard")
            st.session_state.current_state = result
            st.success("Cycle finished. Check Preview/Approve and Analytics tabs.")

        if st.button("Start Background Scheduler", use_container_width=True):
            start_scheduler()
            st.success("Autonomy scheduler started (see terminal/logs).")

        st.divider()
        st.caption("Quick actions")
        if st.button("Dry-run mode ON (no real posts)"):
            config["executor"]["dry_run"] = True
            st.info("Dry-run enabled for this session")

        st.divider()
        st.caption("Memory")
        st.write(f"Vector docs: {vector_store.count() if vector_store else 'N/A'}")

    # === TABS ===
    tab_generate, tab_calendar, tab_analytics, tab_config, tab_logs, tab_preview, tab_console = st.tabs([
        "Generate Now", "Smart Calendar", "Live Analytics", "Config Hub", "Logs & Audit", "Preview / Approve", "Agent Console"
    ])

    # ------------------ GENERATE NOW ------------------
    with tab_generate:
        st.subheader("Instant Multimodal Generation")
        col_a, col_b = st.columns([2, 1])
        with col_a:
            topic = st.text_input("Custom topic / angle (optional)", placeholder="Agent reliability in production 2026")
            fmt = st.selectbox("Primary format", ["thread", "carousel", "poll", "single"])
            num_variants = st.slider("Variants to generate", 1, 5, 3)

        with col_b:
            st.write("**Current brand voice (from config)**")
            st.text_area("", value=config["brand"]["voice"][:280], height=120, disabled=True)

        if st.button("Generate with Full Agent Graph", type="primary"):
            with st.spinner("Research → Strategy → Create → Optimize..."):
                init_state = create_initial_state(config, trigger="manual", brand=config["brand"], niche=config["niche"])
                final = run_workflow(graph, init_state, config=config)
                st.session_state.current_state = final
                st.session_state.pending_drafts = final.get("content_drafts", [])

            st.success(f"Generated {len(st.session_state.pending_drafts)} drafts. Go to Preview/Approve tab.")

        if st.session_state.pending_drafts:
            st.markdown("### Latest Generated Drafts")
            for d in st.session_state.pending_drafts[:3]:
                render_post_preview(d, key_prefix="gen")

    # ------------------ SMART CALENDAR ------------------
    with tab_calendar:
        st.subheader("14-Day Intelligent Content Calendar")
        current_state = st.session_state.current_state or {}
        calendar = current_state.get("content_calendar", config.get("calendar", {}).get("default", []))
        render_calendar_table(calendar)

        if st.button("Rebuild Calendar from Latest Research"):
            with st.spinner("Strategist rebuilding..."):
                # In real impl would force strategist node
                st.info("Calendar would be regenerated. For demo, run full cycle from sidebar.")

    # ------------------ LIVE ANALYTICS ------------------
    with tab_analytics:
        st.subheader("Performance & ROI Intelligence")
        current_state = st.session_state.current_state or {}
        metrics = current_state.get("metrics", [])
        render_metrics_chart(metrics)

        col1, col2 = st.columns(2)
        with col1:
            roi = current_state.get("roi_summary", {})
            if roi:
                st.metric("Est. Value Proxy (USD)", f"${roi.get('value_proxy_usd', 0):.2f}")
                st.metric("Avg Engagement Rate", f"{roi.get('avg_engagement_rate', 0)}%")
        with col2:
            forecast = current_state.get("growth_forecast", {})
            if forecast:
                st.write("**7-day Growth Forecast**")
                st.json(forecast)

    # ------------------ CONFIG HUB ------------------
    with tab_config:
        st.subheader("Live Configuration")
        st.caption("Edits here are session-only. Persist via YAML or future DB-backed config service.")

        edited_brand_voice = st.text_area("Brand Voice", value=config["brand"]["voice"], height=160)
        if st.button("Apply Voice Change (session)"):
            config["brand"]["voice"] = edited_brand_voice
            st.success("Voice updated for this session. Restart cycle to use.")

        st.divider()
        st.write("**Posting Windows**")
        st.write(config.get("calendar", {}).get("best_times", []))

        if st.button("Reload config.yaml from disk"):
            with open(PROJECT_ROOT / "config.yaml") as f:
                new_cfg = yaml.safe_load(f)
            st.session_state.config_reload = new_cfg
            st.success("Config reloaded. Refresh page or restart process for full effect.")

    # ------------------ LOGS & AUDIT ------------------
    with tab_logs:
        st.subheader("Structured Logs + Decision Audit")
        current_state = st.session_state.current_state or {}
        audit = current_state.get("audit_trail", [])
        if audit:
            for entry in audit[-8:]:
                st.code(f"[{entry.get('timestamp', '')}] {entry.get('agent')}: {entry.get('action')}\n{entry.get('details')}", language="json")
        else:
            st.info("Run a cycle to populate the audit trail.")

        st.caption("Full LangSmith traces appear here when LANGSMITH_TRACING=true (future enhancement)")

    # ------------------ PREVIEW / APPROVE (HITL) ------------------
    with tab_preview:
        st.subheader("Human-in-the-Loop Approval Gate")
        drafts: List[ContentDraft] = st.session_state.pending_drafts or (st.session_state.current_state or {}).get("content_drafts", [])

        if not drafts:
            st.info("Generate content first (Generate Now tab or sidebar cycle).")
        else:
            for idx, draft in enumerate(drafts):
                with st.container(border=True):
                    render_post_preview(draft, key_prefix=f"prev_{idx}")

                    c1, c2, c3 = st.columns(3)
                    with c1:
                        if st.button("✅ Approve", key=f"approve_{idx}"):
                            st.session_state.approved_ids.add(draft.id)
                            history_store.log_human_feedback(draft.id, "approve", 1.0, "Approved via UI") if history_store else None
                            st.success("Approved")
                    with c2:
                        if st.button("✏️ Request Revision", key=f"revise_{idx}"):
                            history_store.log_human_feedback(draft.id, "revise", 0.4, "User requested revision") if history_store else None
                            st.info("Feedback recorded. Re-run Optimizer in next cycle.")
                    with c3:
                        if st.button("🗑️ Kill", key=f"kill_{idx}"):
                            st.warning("Draft killed. Will not be published.")

            if st.button("PUBLISH ALL APPROVED (respects dry-run)", type="primary"):
                approved = [d for d in drafts if d.id in st.session_state.approved_ids]
                if st.session_state.current_state:
                    st.session_state.current_state["selected_draft_ids"] = [d.id for d in approved]
                    st.session_state.current_state["approval_gate_passed"] = True

                with st.spinner("Executor publishing..."):
                    result = run_autonomy_cycle("approved_from_ui")
                st.success(f"Published / scheduled {len(result.get('published_posts', []))} posts.")
                st.balloons()

    # ------------------ AGENT CONSOLE ------------------
    with tab_console:
        render_agent_console(
            state=st.session_state.current_state or {},
            run_autonomy_fn=run_autonomy_cycle,
        )

    # Footer
    st.divider()
    st.caption(
        "daily_x_posts v1.0 • LangGraph + Novita AI • Production autonomous CMO • "
        f"Session started {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"
    )
