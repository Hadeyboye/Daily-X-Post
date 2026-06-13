"""
tools/multi_platform.py

Stubs + interfaces for future multi-platform execution (LinkedIn, Instagram, Bluesky, Threads, etc).

For v1 the primary platform is X. All other platforms are safe no-op stubs that log intent.
This allows the rest of the system to plan for multi-platform without breaking.
"""

from __future__ import annotations

from typing import Any, Dict

import structlog

logger = structlog.get_logger(__name__)


class MultiPlatformPoster:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled_platforms = config.get("executor", {}).get("platforms", ["x"])

    def post(self, platform: str, content: Dict[str, Any], dry_run: bool = True) -> Dict[str, Any]:
        if platform not in self.enabled_platforms:
            return {"platform": platform, "status": "disabled"}

        if dry_run:
            logger.info("multi_platform_dry_post", platform=platform, content_keys=list(content.keys()))
            return {"platform": platform, "status": "dry_run_success", "url": f"https://{platform}.example.com/post/mock"}

        # Real implementations go here
        if platform == "linkedin":
            # Would use LinkedIn API or browser
            pass
        elif platform == "bluesky":
            # atproto client
            pass

        logger.info("multi_platform_post_attempt", platform=platform)
        return {"platform": platform, "status": "not_implemented_v1", "note": "Implement real client here"}

    def schedule(self, platform: str, when: str, content: Dict[str, Any]) -> str:
        job_id = f"job_{platform}_{when}"
        logger.info("multi_platform_scheduled", job_id=job_id)
        return job_id


def get_multi_platform_poster(config: Dict[str, Any]) -> MultiPlatformPoster:
    return MultiPlatformPoster(config)
