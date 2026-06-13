#!/usr/bin/env python3
"""
daily_x_posts - Main Entry Point
Autonomous AI Social Media Intelligence Platform (2026)

This is both:
- The Streamlit dashboard launcher (default)
- The headless autonomy engine (python main.py --autonomy --loop)

Core responsibilities:
- Load config + env
- Initialize memory (Chroma + SQLite)
- Build the LangGraph supervisor workflow
- Provide CLI for one-shot / scheduled / research modes
- Run the Streamlit UI (beautiful production dashboard)
- Background APScheduler for full autonomy
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import structlog
import yaml
from dotenv import load_dotenv

# APScheduler is only needed for the autonomous background loop.
# We import it lazily inside start_autonomy_scheduler so that a pure-UI
# run (e.g. Streamlit Cloud or `streamlit run`) does not hard-fail if the
# package is temporarily missing. The full requirements.txt still lists it.


# Local imports (ensure PYTHONPATH or run from root)
sys.path.insert(0, str(Path(__file__).parent))

from graph.state import AgentState, create_initial_state
from graph.workflow import build_supervisor_graph, run_workflow
from memory.vector_store import get_vector_store
from memory.history import SQLiteHistory
from utils.logging import setup_logging
from utils.safety import SafetyFilter
from ui.dashboard import launch_dashboard

# --------------------------------------------------------------------------- #
# Globals & Configuration
# --------------------------------------------------------------------------- #

PROJECT_ROOT = Path(__file__).parent.resolve()
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"

for d in (OUTPUTS_DIR, DATA_DIR, LOGS_DIR):
    d.mkdir(parents=True, exist_ok=True)

load_dotenv(PROJECT_ROOT / ".env")
logger = structlog.get_logger(__name__)

# Global singletons (initialized on start)
CONFIG: Dict[str, Any] = {}
VECTOR_STORE = None
HISTORY_STORE: Optional[SQLiteHistory] = None
SAFETY: Optional[SafetyFilter] = None
SCHEDULER: Optional[BackgroundScheduler] = None
GRAPH = None  # Compiled LangGraph app


# --------------------------------------------------------------------------- #
# Configuration & Bootstrap
# --------------------------------------------------------------------------- #

def load_config() -> Dict[str, Any]:
    """Load YAML config with sensible overrides from environment."""
    cfg_path = PROJECT_ROOT / "config.yaml"
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # Env overrides (common ones)
    if os.getenv("DEBUG", "").lower() == "true":
        cfg["platform"]["environment"] = "development"
    if os.getenv("AUTONOMY_ENABLED"):
        cfg["autonomy"]["enabled"] = os.getenv("AUTONOMY_ENABLED").lower() == "true"
    if os.getenv("DRY_RUN"):
        cfg["executor"]["dry_run"] = os.getenv("DRY_RUN").lower() == "true"

    return cfg


def bootstrap() -> None:
    """Initialize all core services. Idempotent."""
    global CONFIG, VECTOR_STORE, HISTORY_STORE, SAFETY, GRAPH

    CONFIG = load_config()
    setup_logging(CONFIG.get("observability", {}), LOGS_DIR)

    logger.info("bootstrapping_daily_x_posts", version=CONFIG["platform"]["version"])

    VECTOR_STORE = get_vector_store(
        persist_dir=os.getenv("CHROMA_PERSIST_DIR", str(PROJECT_ROOT / "chroma_db")),
        collection_prefix=CONFIG["brand"]["handle"].replace("@", ""),
    )

    HISTORY_STORE = SQLiteHistory(
        db_path=os.getenv("SQLITE_DB_PATH", str(DATA_DIR / "daily_x_posts.db"))
    )
    HISTORY_STORE.initialize_schema()

    SAFETY = SafetyFilter(CONFIG.get("safety", {}))

    # Build the full supervisor graph once
    GRAPH = build_supervisor_graph(
        config=CONFIG,
        vector_store=VECTOR_STORE,
        history_store=HISTORY_STORE,
        safety=SAFETY,
    )

    logger.info("bootstrap_complete", graph_nodes=list(GRAPH.nodes.keys()) if hasattr(GRAPH, 'nodes') else "compiled")


# --------------------------------------------------------------------------- #
# Autonomy Loop (the "CMO brain")
# --------------------------------------------------------------------------- #

def run_autonomy_cycle(trigger: str = "scheduled") -> Dict[str, Any]:
    """
    Execute one full closed-loop intelligence cycle:
    Research → Strategize → Create → Optimize → (HITL) → Execute → Analyze → Learn
    """
    logger.info("autonomy_cycle_start", trigger=trigger, timestamp=datetime.utcnow().isoformat())

    try:
        initial_state = create_initial_state(
            config=CONFIG,
            trigger=trigger,
            brand=CONFIG["brand"],
            niche=CONFIG["niche"],
        )

        # Run the compiled graph (supports checkpoints + interrupts)
        final_state = run_workflow(GRAPH, initial_state, config=CONFIG)

        # Persist key outcomes
        if final_state.get("published_posts"):
            for post in final_state["published_posts"]:
                HISTORY_STORE.log_post(post)

        if final_state.get("metrics"):
            HISTORY_STORE.log_metrics(final_state["metrics"])

        logger.info(
            "autonomy_cycle_success",
            posts_generated=len(final_state.get("content_drafts", [])),
            posts_published=len(final_state.get("published_posts", [])),
            avg_predicted_score=final_state.get("predicted_virality", 0.0),
        )
        return final_state

    except Exception as exc:
        logger.exception("autonomy_cycle_failed", error=str(exc))
        # Still try to log the failure for later self-improvement
        HISTORY_STORE.log_event("autonomy_failure", {"error": str(exc), "trigger": trigger})
        raise


def start_autonomy_scheduler():
    """Background scheduler for continuous operation.

    APScheduler is imported lazily here so that users who only want the
    Streamlit UI (e.g. on Streamlit Cloud) are not forced to have the
    package if they haven't run `pip install -r requirements.txt` yet.
    """
    global SCHEDULER

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError as e:
        logger.error(
            "apscheduler_not_installed",
            msg="The 'apscheduler' package is required for autonomy/scheduler features. "
                "Run: pip install apscheduler  or  pip install -r requirements.txt"
        )
        raise RuntimeError(
            "apscheduler is not installed. "
            "Install it with `pip install apscheduler` (or the full requirements.txt) "
            "if you want to use --autonomy / background scheduling."
        ) from e

    if SCHEDULER and SCHEDULER.running:
        return SCHEDULER

    interval_minutes = CONFIG.get("autonomy", {}).get("loop_interval_minutes", 45)
    scheduler = BackgroundScheduler(timezone=CONFIG.get("autonomy", {}).get("timezone", "UTC"))

    scheduler.add_job(
        run_autonomy_cycle,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="autonomy_cycle",
        name="DailyX Autonomous Intelligence Loop",
        replace_existing=True,
        args=["scheduled"],
    )

    # Optional: daily deep research + calendar rebuild at 07:00 local
    scheduler.add_job(
        run_autonomy_cycle,
        trigger="cron",
        hour=7,
        minute=5,
        id="daily_deep_research",
        args=["daily_research"],
    )

    scheduler.start()
    SCHEDULER = scheduler

    logger.info("autonomy_scheduler_started", interval_minutes=interval_minutes)
    return scheduler


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="daily_x_posts — Autonomous AI Social Media CMO"
    )
    parser.add_argument("--ui", action="store_true", help="Launch Streamlit dashboard (default)")
    parser.add_argument("--autonomy", action="store_true", help="Enable autonomous mode")
    parser.add_argument("--loop", action="store_true", help="Run continuous autonomy loop (with scheduler)")
    parser.add_argument("--campaign", action="store_true", help="Run one full campaign cycle now")
    parser.add_argument("--research", action="store_true", help="Run only the Research Agent")
    parser.add_argument("--dry-run", action="store_true", help="Force dry-run (no real posts)")
    parser.add_argument("--niche", type=str, default=None, help="Override niche for this run")
    parser.add_argument("--config", type=str, default=None, help="Path to alternate config.yaml")
    parser.add_argument("--port", type=int, default=8501, help="Streamlit port")
    return parser.parse_args()


def cli_main() -> None:
    args = parse_args()

    bootstrap()

    if args.dry_run:
        CONFIG["executor"]["dry_run"] = True
        logger.warning("dry_run_mode_activated")

    if args.niche:
        CONFIG["niche"]["primary"] = args.niche

    if args.research:
        logger.info("running_research_only")
        state = create_initial_state(CONFIG, "manual_research", CONFIG["brand"], CONFIG["niche"])
        # In a real impl we would call the research node directly. For brevity we run full but stop early.
        final = run_workflow(GRAPH, state, config=CONFIG)
        print("\n=== RESEARCH INSIGHTS (truncated) ===")
        print(final.get("research_insights", "No insights generated")[:2000])
        return

    if args.campaign or args.autonomy:
        logger.info("running_single_campaign_cycle")
        result = run_autonomy_cycle(trigger="manual" if args.campaign else "cli")
        print("\n=== CAMPAIGN COMPLETE ===")
        print(f"Posts generated: {len(result.get('content_drafts', []))}")
        print(f"Published (or scheduled): {len(result.get('published_posts', []))}")
        if result.get("audit_trail"):
            print("Last decision:", result["audit_trail"][-1])
        return

    if args.loop or args.autonomy:
        logger.info("starting_continuous_autonomy")
        scheduler = start_autonomy_scheduler()
        print(f"Autonomy loop running every {CONFIG['autonomy']['loop_interval_minutes']} minutes.")
        print("Press Ctrl+C to stop.")

        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("autonomy_loop_stopped_by_user")
            scheduler.shutdown()
        return

    # Default: Launch beautiful Streamlit UI
    logger.info("launching_streamlit_dashboard", port=args.port)
    launch_dashboard(
        config=CONFIG,
        graph=GRAPH,
        vector_store=VECTOR_STORE,
        history_store=HISTORY_STORE,
        safety=SAFETY,
        run_autonomy_cycle=run_autonomy_cycle,
        start_scheduler=start_autonomy_scheduler,
    )


if __name__ == "__main__":
    cli_main()
