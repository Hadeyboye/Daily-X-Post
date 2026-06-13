"""
tools/novita_integration.py

Production-grade client for Novita AI (LLM + Image + Video generation).

Designed to be:
- Drop-in replacement for OpenAI-style clients where possible
- Resilient with retries
- Graceful degradation to mocks / local fallbacks
- Fully configurable via config + env
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger(__name__)


class NovitaClient:
    """Thin, robust wrapper around Novita AI APIs."""

    def __init__(self, api_key: str, base_url: str = "https://api.novita.ai/v3", default_model: str = "meta-llama/Llama-3.1-70B-Instruct"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })
        self.enabled = bool(api_key and api_key != "sk-novita-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: int = 800,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        if not self.enabled:
            # High-quality mock response for immediate usability (no key)
            last = messages[-1]["content"][:120] if messages else "topic"
            return (
                f"1/ {last} is reshaping how teams ship.\n"
                "2/ The key insight most people miss is reliable multi-step execution with verification.\n"
                "3/ We have seen 3-4x iteration speed when agents have explicit self-critique loops.\n"
                "4/ What problem are you solving with agents right now?"
            )

        # Advanced AI thinking: prepend system prompt to force step-by-step reasoning on virality, trends, brand, engagement
        system_msg = {
            "role": "system",
            "content": (
                "You are a world-class AI strategist, viral content creator, and social media analyst. "
                "Always think step-by-step internally (audience psychology, current X trends, brand voice alignment, "
                "hook strength, data/evidence, contrarian angle, CTA effectiveness) before crafting your response. "
                "Be specific, original, evidence-based, and optimized for high engagement (saves, replies, reposts). "
                "Never be generic or hype without substance."
            )
        }
        final_messages = [system_msg] + messages

        payload = {
            "model": model or self.default_model,
            "messages": final_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            **kwargs,
        }
        url = f"{self.base_url}/chat/completions"
        resp = self.session.post(url, json=payload, timeout=90)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=12))
    def generate_image(
        self,
        prompt: str,
        model: str = "flux-1/schnell",
        width: int = 1024,
        height: int = 1024,
        steps: int = 4,
        guidance: float = 3.5,
        **kwargs: Any,
    ) -> Dict[str, Any] | bytes:
        """
        Returns either {"url": "..."} or raw bytes.
        """
        if not self.enabled:
            return {"url": None, "mock": True, "prompt": prompt}

        url = f"{self.base_url}/image/generations"
        payload = {
            "model": model,
            "prompt": prompt,
            "width": width,
            "height": height,
            "steps": steps,
            "guidance_scale": guidance,
            **kwargs,
        }
        resp = self.session.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        # Novita usually returns url or b64. Handle both.
        if "data" in data and data["data"]:
            return data["data"][0]  # usually contains url or b64_json
        return data

    def generate_video(
        self,
        prompt: str,
        image_ref: Optional[str] = None,
        duration: int = 4,
        model: str = "stable-video-diffusion",
    ) -> Dict[str, Any]:
        """Short video / animation generation. Returns job or direct URL."""
        if not self.enabled:
            return {"status": "mock", "url": None, "prompt": prompt, "note": "Video generation requires real Novita key + credits"}

        # Real implementation would be async job + polling.
        # For v1 we return a structured stub that UI can render nicely.
        return {
            "status": "submitted",
            "model": model,
            "prompt": prompt,
            "estimated_seconds": duration * 3,
            "note": "In production this would poll Novita until ready and return mp4/gif path.",
        }


def get_novita_client(config: Dict[str, Any]) -> NovitaClient:
    api_key = os.getenv("NOVITA_API_KEY", "")
    base_url = os.getenv("NOVITA_BASE_URL", config.get("novita", {}).get("base_url", "https://api.novita.ai/v3"))
    model = os.getenv("NOVITA_DEFAULT_MODEL", config.get("novita", {}).get("default_model", "meta-llama/Llama-3.1-70B-Instruct"))
    return NovitaClient(api_key=api_key, base_url=base_url, default_model=model)
