"""
ui package

Streamlit production dashboard for daily_x_posts.

Modular components + main dashboard with 7 professional tabs.
"""

from .components import (
    render_post_preview,
    render_metrics_chart,
    render_calendar_table,
    render_agent_console,
    render_safety_banner,
)
from .dashboard import launch_dashboard

__all__ = [
    "render_post_preview",
    "render_metrics_chart",
    "render_calendar_table",
    "render_agent_console",
    "render_safety_banner",
    "launch_dashboard",
]
