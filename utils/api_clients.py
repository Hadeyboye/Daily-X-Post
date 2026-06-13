import os
from typing import Optional, Dict, Any
import requests
from dotenv import load_dotenv

load_dotenv()

class APIClient:
    """Unified API client for all external services in Daily-X-Post."""

    def __init__(self):
        self.novita_api_key = os.getenv("NOVITA_API_KEY")
        self.novita_base_url = os.getenv("NOVITA_BASE_URL", "https://api.novita.ai/v3")
        
        self.x_api_key = os.getenv("X_API_KEY")
        self.x_api_secret = os.getenv("X_API_SECRET")
        self.x_access_token = os.getenv("X_ACCESS_TOKEN")
        self.x_access_token_secret = os.getenv("X_ACCESS_TOKEN_SECRET")
        self.x_bearer_token = os.getenv("X_BEARER_TOKEN")
        
        self.langsmith_api_key = os.getenv("LANGSMITH_API_KEY")

    # ====================== NOVITA (Images, Video, LLM) ======================
    def novita_post(self, endpoint: str, payload: Dict, timeout: int = 60) -> Dict:
        """General Novita API caller."""
        if not self.novita_api_key:
            raise ValueError("NOVITA_API_KEY not set")
        
        headers = {
            "Authorization": f"Bearer {self.novita_api_key}",
            "Content-Type": "application/json"
        }
        url = f"{self.novita_base_url}/{endpoint.lstrip('/')}"
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def generate_image(self, prompt: str, model: str = None, width: int = 1024, height: int = 1024) -> str:
        """Flux image generation."""
        model = model or os.getenv("NOVITA_IMAGE_MODEL", "flux-1/schnell")
        payload = {
            "model_name": model,
            "prompt": prompt,
            "width": width,
            "height": height,
            "num_images": 1,
            "seed": -1
        }
        result = self.novita_post("image-generation", payload)
        return result["images"][0]["image_url"]  # adjust based on actual response

    def chat_completion(self, messages: list, model: str = None, max_tokens: int = 800, temperature: float = 0.7) -> str:
        """LLM chat completion via Novita (OpenAI compatible)."""
        model = model or os.getenv("NOVITA_DEFAULT_MODEL", "meta-llama/Llama-3.1-70B-Instruct")
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        result = self.novita_post("chat/completions", payload)
        return result["choices"][0]["message"]["content"].strip()

    # ====================== X / TWITTER ======================
    def x_post_tweet(self, text: str, media_ids: list = None) -> Dict:
        """Post to X using v2 API."""
        if not self.x_bearer_token:
            raise ValueError("X_BEARER_TOKEN not set")
        
        url = "https://api.twitter.com/2/tweets"
        headers = {
            "Authorization": f"Bearer {self.x_bearer_token}",
            "Content-Type": "application/json"
        }
        payload = {"text": text}
        if media_ids:
            payload["media"] = {"media_ids": media_ids}
        
        resp = requests.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()

    def x_search_recent(self, query: str, max_results: int = 10) -> list:
        """Search recent tweets (for live research)."""
        if not self.x_bearer_token:
            return []
        url = f"https://api.twitter.com/2/tweets/search/recent?query={query}&max_results={max_results}&tweet.fields=public_metrics,created_at"
        headers = {"Authorization": f"Bearer {self.x_bearer_token}"}
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            return resp.json().get("data", [])
        return []

    # ====================== LANGSMITH ======================
    def log_langsmith(self, run_id: str, data: Dict):
        """Optional: Send custom traces/metrics."""
        if not self.langsmith_api_key:
            return
        # Use LangChain's built-in tracing instead when possible
        pass

    # Add more methods as needed (e.g. web search, etc.)

# Global singleton
api = APIClient()
