"""
tools/browser_tools.py

Playwright-based resilient browser automation fallback.

Used when:
- X API is rate limited or restricted
- Need to perform complex actions (quote tweets, reply chains, poll creation with images)
- Future: LinkedIn / other platforms that lack good APIs

All functions are async-friendly and include strong timeouts + stealth.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import structlog
from playwright.async_api import async_playwright, Browser, Page

logger = structlog.get_logger(__name__)


class BrowserTools:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._browser: Optional[Browser] = None

    async def _get_browser(self) -> Browser:
        if self._browser:
            return self._browser
        p = await async_playwright().start()
        self._browser = await p.chromium.launch(headless=self.headless, args=["--disable-blink-features=AutomationControlled"])
        return self._browser

    async def post_tweet_via_browser(self, text: str, cookies: Optional[Dict] = None) -> Dict[str, Any]:
        """Last-resort posting mechanism. Requires valid session cookies (advanced use)."""
        browser = await self._get_browser()
        context = await browser.new_context()
        if cookies:
            await context.add_cookies(cookies)
        page: Page = await context.new_page()

        try:
            await page.goto("https://x.com/compose/tweet", wait_until="networkidle", timeout=25000)
            await page.fill('div[role="textbox"]', text)
            await page.click('div[data-testid="tweetButton"]')
            await page.wait_for_timeout(2500)
            url = page.url
            return {"success": True, "url": url, "method": "browser"}
        except Exception as e:
            logger.error("browser_post_failed", error=str(e))
            return {"success": False, "error": str(e), "method": "browser"}
        finally:
            await context.close()

    async def close(self):
        if self._browser:
            await self._browser.close()


def get_browser_tools() -> BrowserTools:
    return BrowserTools()
