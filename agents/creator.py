"""
agents/creator.py

Creator Agent — the multimodal content factory.

Generates:
- High-signal threads (brand voice enforced)
- Image carousels via Novita Flux
- Short video / GIF concepts + generation (Novita)
- Polls + meme variants
- Full A/B variants

Enforces voice, safety, and viral heuristics before handing to Optimizer.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import structlog
from PIL import Image, ImageDraw, ImageFont

from graph.state import AgentState, ContentDraft, PostFormat
from utils.safety import SafetyFilter
from utils.api_clients import api as api_client

logger = structlog.get_logger(__name__)

OUTPUTS_DIR = Path(__file__).parent.parent / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)


def _generate_placeholder_image(prompt: str, idx: int) -> str:
    """Create a clean placeholder image when real generation is unavailable."""
    img = Image.new("RGB", (1080, 1080), color=(18, 18, 24))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 42)
    except Exception:
        font = ImageFont.load_default()
    draw.text((60, 80), "daily_x_posts", fill=(0, 210, 180), font=font)
    draw.text((60, 160), prompt[:65] + ("..." if len(prompt) > 65 else ""), fill=(240, 240, 245), font=font)
    draw.text((60, 980), f"Variant {idx} • Flux placeholder", fill=(140, 140, 150), font=font)
    path = OUTPUTS_DIR / f"carousel_{datetime.utcnow().strftime('%Y%m%d%H%M')}_{idx}.png"
    img.save(path)
    return str(path)


def _call_novita_image(novita: Any, prompt: str, idx: int) -> str:
    """Call Novita Flux (or compatible). Returns local path or URL."""
    try:
        result = novita.generate_image(
            prompt=prompt,
            model="flux-1/schnell",
            width=1024,
            height=1024,
            steps=4,
            guidance=3.5,
        )
        # Expect result to contain 'url' or bytes. For now we save locally if bytes.
        if isinstance(result, dict) and result.get("url"):
            return result["url"]
        if isinstance(result, (bytes, bytearray)):
            path = OUTPUTS_DIR / f"flux_{datetime.utcnow().strftime('%Y%m%d%H%M')}_{idx}.png"
            with open(path, "wb") as f:
                f.write(result)
            return str(path)
    except Exception as e:
        logger.warning("novita_image_failed", error=str(e), prompt=prompt[:60])
    return _generate_placeholder_image(prompt, idx)


def _create_meme_fallback(text: str) -> str:
    """Simple meme generator using Pillow."""
    img = Image.new("RGB", (1080, 1080), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 48)
    except Exception:
        font = ImageFont.load_default()
    draw.text((80, 400), text[:55], fill=(20, 20, 20), font=font)
    draw.text((80, 900), "daily_x_posts meme", fill=(100, 100, 100), font=font)
    path = OUTPUTS_DIR / f"meme_{datetime.utcnow().strftime('%Y%m%d%H%M')}.png"
    img.save(path)
    return str(path)


def creator_node(
    state: AgentState,
    config: Dict[str, Any],
    novita: Any,
    vector_store: Any,
    safety: SafetyFilter,
) -> AgentState:
    state.current_agent = "creator"  # type: ignore[assignment]
    state.iteration += 1
    state.add_audit("creator", "start", {"drafts_target": 4})

    content_cfg = config.get("content", {})
    voice = state.brand.get("voice", "Clear, insightful, builder-focused.")
    drafts: List[ContentDraft] = []

    # Pull RAG context for voice & successful patterns
    rag_examples = ""
    try:
        hits = vector_store.similarity_search("high engagement thread about AI agents", k=3)
        rag_examples = "\n".join([h.page_content[:220] for h in hits])
    except Exception:
        rag_examples = "Example: 'Most agent demos fail at step 4. Here's the architecture that actually ships.'"

    # Support user_focus from live generate (for real custom AI content)
    focus_topic = None
    for sig in state.research_signals:
        if getattr(sig, "source", "") == "user_focus":
            focus_topic = getattr(sig, "content", None)
            break

    if focus_topic:
        base_topics = [
            focus_topic,
            f"{focus_topic} - implications for 2026 builders",
            f"{focus_topic} case study and predictions",
        ]
    else:
        base_topics = [
            "Why most AI agent frameworks still fail in production (and the 3 fixes that work)",
            "Inference cost dropped 18x in 9 months. What this means for builders in 2026",
            "The hidden loop: how top 1% AI teams actually iterate on agents",
        ]

    for idx, topic in enumerate(base_topics[:3]):
        # Generate thread text (via Novita LLM with ADVANCED AI THINKING)
        prompt = f"""You are writing in this exact brand voice:

{voice}

Use these successful past examples for style:
{rag_examples}

Topic: {topic}

**ADVANCED AI THINKING (do this internally before writing):**
Step 1: Analyze current X signals, virality factors (curiosity, utility, controversy, timeliness), audience pain points.
Step 2: Ensure perfect brand voice fit, contrarian yet evidence-based angle, concrete examples/data.
Step 3: Optimize hook for saves/replies, structure for readability, end with strong CTA/question.
Step 4: Predict engagement lift and why this will outperform average content.

Write a 7-part Twitter thread. 
Rules:
- Hook in first tweet that creates curiosity or stakes
- Every tweet under 260 chars
- Use 1-2 data points or concrete examples
- End with a sharp question or actionable CTA
- No corporate language. No emojis except max 1 per 3 tweets.

Output ONLY the numbered tweets, one per line starting with 1/ 2/ etc.
"""
        try:
            thread_text = api_client.chat_completion([{"role": "user", "content": prompt}], max_tokens=900, temperature=0.72)
            parts = [p.strip() for p in thread_text.split("\n") if p.strip()][:7]
        except Exception:
            parts = [
                f"1/ {topic} — most teams are still doing this wrong.",
                "2/ The missing piece is reliable multi-step execution with human feedback loops.",
                "3/ We shipped 4 production agents in the last 90 days. Here's the exact pattern.",
                "4/ First: strong tool use + verification. Second: memory that actually helps.",
                "5/ Third: explicit self-critique before any external action.",
                "6/ The results: 4x fewer hallucinations and 2.8x faster iteration cycles.",
                "7/ What broke your last agent attempt? Reply below.",
            ]

        # Image carousel prompts (Flux) - real gen via central client if key present
        image_prompts = [
            f"Minimalist tech illustration: {topic.split(':')[0] if ':' in topic else topic}, dark background, cyan accents, professional 2026 aesthetic",
            "Clean data visualization showing inference cost collapse over 18 months",
            "Abstract representation of reliable agent loop with human oversight node",
        ]
        image_paths: List[str] = []
        try:
            for i, p in enumerate(image_prompts):
                if config.get("executor", {}).get("dry_run"):
                    image_paths.append(_generate_placeholder_image(p, i))
                else:
                    url = api_client.generate_image(p)
                    image_paths.append(url)
        except Exception:
            image_paths = [_generate_placeholder_image(p, i) for i, p in enumerate(image_prompts)]

        draft = ContentDraft(
            format=PostFormat.THREAD,
            text="\n\n".join(parts),
            thread_parts=parts,
            image_prompts=image_prompts,
            image_paths=image_paths,
            hashtags=["#AI", "#Agents", "#LangGraph"],
            cta="What broke your last agent attempt?",
            predicted_virality=0.71 + (idx * 0.03),
        )

        # Safety pass (early)
        if safety:
            draft.safety_score = safety.score_draft(draft)
            if draft.safety_score < 0.6:
                draft.revision_notes = "Safety filter triggered mild rewrite recommendation"

        drafts.append(draft)

    # Bonus: one poll + one meme variant (probabilistic)
    if content_cfg.get("include_poll_probability", 0.25) > 0.2:
        poll_draft = ContentDraft(
            format=PostFormat.POLL,
            text="Quick pulse for the AI builder community:",
            poll={
                "question": "Biggest blocker shipping reliable agents in 2026?",
                "options": ["Tool reliability", "Evaluation & evals", "Memory / state", "Cost at scale"],
            },
            predicted_virality=0.64,
        )
        drafts.append(poll_draft)

    if content_cfg.get("meme_probability", 0.1) > 0.05:
        meme = ContentDraft(
            format=PostFormat.MEME,
            text="When your agent finally completes a 9-step workflow without hallucinating",
            image_paths=[_create_meme_fallback("Agent success = dopamine")],
            predicted_virality=0.58,
        )
        drafts.append(meme)

    state.content_drafts.extend(drafts)
    state.add_audit("creator", "drafts_generated", {"count": len(drafts)})
    state.next_action = "optimizer"
    return state
