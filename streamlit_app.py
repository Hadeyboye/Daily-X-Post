"""
streamlit_app.py

Proper entry point for Streamlit Community Cloud and local `streamlit run`.

This file:
- Sets up the Python path
- Calls bootstrap() to initialize config, memory, graph, safety
- Directly launches the dashboard UI (the full hero + demo + 7 tabs experience)

This avoids CLI argument parsing and ensures the Streamlit page actually renders.
"""

import os
import sys
from pathlib import Path

# Prevent protobuf 4.x "Descriptors cannot be created directly" errors with ChromaDB (common on Streamlit Cloud / fresh installs)
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

# Ensure local imports work when deployed on Streamlit Cloud or run from any cwd
sys.path.insert(0, str(Path(__file__).parent))

# 1. Bootstrap (loads config, creates dirs, builds the LangGraph, inits Chroma/SQLite, etc.)
from main import bootstrap
bootstrap()

# 2. Pull the initialized singletons that launch_dashboard expects
from main import (
    CONFIG,
    GRAPH,
    VECTOR_STORE,
    HISTORY_STORE,
    SAFETY,
    run_autonomy_cycle,
    start_autonomy_scheduler,
)

# 3. Launch the actual dashboard (this contains all the st. calls, hero, demo button, tabs, etc.)
from main import launch_dashboard

launch_dashboard(
    config=CONFIG,
    graph=GRAPH,
    vector_store=VECTOR_STORE,
    history_store=HISTORY_STORE,
    safety=SAFETY,
    run_autonomy_cycle=run_autonomy_cycle,
    start_scheduler=start_autonomy_scheduler,
)
