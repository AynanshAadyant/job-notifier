"""Dynamic browser fetcher powered by Scrapling DynamicFetcher."""

import asyncio
from typing import Any, Callable
from fetching.fetcher_interface import PageFetcher, FetchResult


class DynamicFetcher(PageFetcher):
    """Headless Chromium browser fetcher for SPA and JavaScript-heavy pages."""

    def __init__(self, headless: bool = True, network_idle: bool = True, timeout: int = 45000):
        self.headless = headless
        self.network_idle = network_idle
        self.timeout = timeout

    async def fetch(self, url: str, **kwargs: Any) -> FetchResult:
        headless = kwargs.get("headless", self.headless)
        network_idle = kwargs.get("network_idle", self.network_idle)
        timeout = kwargs.get("timeout", self.timeout)
        page_action: Callable[[Any], None] | None = kwargs.get("page_action")

        def _do_fetch() -> FetchResult:
            try:
                from scrapling.fetchers import DynamicFetcher as ScraplingDynamicFetcher
                resp = ScraplingDynamicFetcher.fetch(
                    url,
                    headless=headless,
                    network_idle=network_idle,
                    timeout=timeout,
                    page_action=page_action,
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
