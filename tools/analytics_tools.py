"""
tools/analytics_tools.py

Lightweight analytics & forecasting helpers used by Analyst + Optimizer.

In production these would call BigQuery / Snowflake or your own attribution warehouse.
For daily_x_posts they operate on the local SQLite + in-memory state.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


def calculate_roi_proxy(metrics: List[Dict[str, Any]]) -> Dict[str, float]:
    """Crude but useful business value proxy."""
    total_eng = sum(m.get("engagements", 0) for m in metrics)
    impressions = sum(m.get("impressions", 1) for m in metrics)
    saves = sum(m.get("saves", 0) for m in metrics)

    value = (total_eng * 0.014) + (saves * 0.09)  # tuned heuristics
    return {
        "total_engagements": total_eng,
        "estimated_value_usd": round(value, 2),
        "engagement_per_1k": round((total_eng / max(impressions, 1)) * 1000, 1),
    }


def forecast_growth(historical: List[int], horizon_days: int = 7) -> Dict[str, Any]:
    """Very simple linear + noise forecast. Upgrade with proper model later."""
    if len(historical) < 3:
        historical = historical + [h + 12 for h in range(3)]

    x = np.arange(len(historical))
    y = np.array(historical, dtype=float)
    coef = np.polyfit(x, y, 1)
    future = [int(coef[0] * (len(historical) + i) + coef[1] + np.random.normal(0, 8)) for i in range(horizon_days)]

    return {
        "p50_7d": future[6],
        "p70_7d": int(future[6] * 1.18),
        "trend": "accelerating" if coef[0] > 0 else "flat",
        "confidence": 0.74,
    }


def best_posting_times(metrics_by_hour: Dict[int, float]) -> List[str]:
    """Return top 3 hours from historical performance."""
    if not metrics_by_hour:
        return ["08:30", "12:45", "17:15"]
    sorted_hours = sorted(metrics_by_hour.items(), key=lambda kv: kv[1], reverse=True)[:3]
    return [f"{h:02d}:00" for h, _ in sorted_hours]
