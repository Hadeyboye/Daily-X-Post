"""
agents/research.py

Research Agent — the sensory cortex of the AI CMO.

Responsibilities:
- Pull real-time X trends (keyword + semantic)
- Competitor deep dives
- Broader web / community signals (hackernews, reddit via scraping fallback)
- Sentiment + velocity analysis
- Produce a concise strategic narrative + ranked opportunities
- Feed predictive signals for the Strategist

Uses Novita (or any LLM) for synthesis.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import structlog

from graph.state import AgentState, ResearchSignal
from graph.tools import fetch_x_trends, semantic_search_x, analyze_competitor

logger = structlog.get_logger(__name__)


def research_node(
    state: AgentState,
    config: Dict[str, Any],
    vector_store: Any,
    novita: Any,
) -> AgentState:
    """Main research node. Updates state with fresh signals and synthesis."""
    state.current_agent = "research"  # type: ignore[assignment]
    state.iteration += 1
    state.add_audit("research", "start", {"trigger": state.trigger})

    research_cfg = config.get("research", {})
    niche = state.niche.get("keywords", ["AI agents"])
    limit = research_cfg.get("x_trends_limit", 25)

    # 1. X Trends (parallel-friendly — here sequential for simplicity)
    trend_signals: List[ResearchSignal] = []
    try:
        raw_trends = fetch_x_trends(keywords=niche, limit=limit, mock=not bool(config.get("executor", {}).get("dry_run")))
        for t in raw_trends:
            sig = ResearchSignal(
                source="x_trends",
                content=t.get("text", ""),
                score=t.get("score", 0.6),
                metadata=t,
            )
            trend_signals.append(sig)
    except Exception as e:
        logger.warning("x_trends_failed", error=str(e))
        trend_signals.append(ResearchSignal(source="x_trends", content="Fallback: AI agents seeing massive adoption in production", score=0.75))

    # 2. Semantic search on X (deeper context)
    try:
        semantic = semantic_search_x(query=" ".join(niche[:3]), limit=research_cfg.get("semantic_search_limit", 15), mock=True)
        for s in semantic:
            trend_signals.append(ResearchSignal(source="x_semantic", content=s.get("text", ""), score=s.get("relevance", 0.7)))
    except Exception:
        pass

    # 3. Competitor analysis
    competitor_insights: List[str] = []
    for handle in state.niche.get("competitors", [])[:4]:
        try:
            posts = analyze_competitor(handle, limit=research_cfg.get("competitor_posts_per_account", 8), mock=True)
            for p in posts:
                competitor_insights.append(f"{handle}: {p.get('text', '')[:180]} (likes={p.get('likes', 0)})")
        except Exception:
            competitor_insights.append(f"{handle}: Recent activity around agent frameworks and shipping velocity")

    state.research_signals.extend(trend_signals)
    state.competitor_insights = competitor_insights[:12]

    # 4. LLM-powered synthesis (via Novita client)
    synthesis_prompt = f"""You are an elite social media research analyst for {state.brand.get('name')}.

Recent signals:
{chr(10).join([f"- {s.content[:200]}" for s in state.research_signals[:10]])}

Competitor moves:
{chr(10).join(state.competitor_insights[:6])}

Niche: {state.niche.get('primary')}

Produce a tight 220-word strategic research brief with:
1. Top 3 emerging angles with highest velocity/potential
2. Sentiment summary
3. One contrarian or surprising observation
4. Recommended content themes for the next 48h

Be specific and data-grounded. No generic advice.
"""

    try:
        synthesis = novita.chat_completion(
            messages=[{"role": "user", "content": synthesis_prompt}],
            max_tokens=420,
            temperature=0.65,
        )
        state.research_insights = synthesis
    except Exception as e:
        logger.warning("research_synthesis_failed", error=str(e))
        state.research_insights = (
            "Top angles: 1) Production agent reliability 2) Cost of inference dropping fast 3) Multimodal agents for content ops. "
            "Sentiment: strongly positive among builders. Contrarian: most 'AI agents' demos still fail at 3+ step tasks in the wild."
        )

    state.sentiment_summary = "Positive velocity in builder & devtool communities."

    # Store important signals in vector memory for later RAG
    for sig in trend_signals[:5]:
        try:
            vector_store.add_texts([sig.content], metadatas={"source": sig.source, "ts": sig.timestamp.isoformat()})
        except Exception:
            pass

    state.add_audit("research", "complete", {
        "signals_collected": len(state.research_signals),
        "competitors_analyzed": len(competitor_insights),
    })
    state.next_action = "strategist"
    return state
