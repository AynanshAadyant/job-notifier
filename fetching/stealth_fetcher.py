"""Stealth fetcher implementation powered by Scrapling StealthyFetcher."""

import asyncio
from typing import Any
from fetching.fetcher_interface import PageFetcher, FetchResult


class StealthFetcher(PageFetcher):
    """Fetcher capable of handling Cloudflare, anti-bot systems, and bot mitigations."""

    def __init__(self, headless: bool = True, solve_cloudflare: bool = True, timeout: int = 60000):
        self.headless = headless
        self.solve_cloudflare = solve_cloudflare
        self.timeout = timeout

    async def fetch(self, url: str, **kwargs: Any) -> FetchResult:
        headless = kwargs.get("headless", self.headless)
        solve_cloudflare = kwargs.get("solve_cloudflare", self.solve_cloudflare)
        timeout = kwargs.get("timeout", self.timeout)

        def _do_fetch() -> FetchResult:
            try:
                from scrapling.fetchers import StealthyFetcher
                resp = StealthyFetcher.fetch(
                    url,
                    headless=headless,
                    solve_cloudflare=solve_cloudflare,
                    timeout=timeout,
                )
                return FetchResult(
                    url=str(resp.url),
                    status_code=int(resp.status),
                    text=resp.text,
                    headers=dict(resp.headers) if hasattr(resp, "headers") else {},
                    is_success=200 <= int(resp.status) < 400,
                    response_obj=resp,
                )
            except Exception as e:
                return FetchResult(
                    url=url,
                    status_code=0,
                    text="",
                    headers={},
                    is_success=False,
                    error_message=str(e),
                )

        return await asyncio.to_thread(_do_fetch)
