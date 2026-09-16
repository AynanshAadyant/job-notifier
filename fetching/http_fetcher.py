"""Static HTTP fetcher implementation powered by Scrapling Fetcher."""

import asyncio
from typing import Any
from fetching.fetcher_interface import PageFetcher, FetchResult


class HttpFetcher(PageFetcher):
    """High-speed static HTTP fetcher using Scrapling's Fetcher (curl_cffi backend)."""

    def __init__(self, timeout: int = 30, stealthy_headers: bool = True):
        self.timeout = timeout
        self.stealthy_headers = stealthy_headers

    async def fetch(self, url: str, **kwargs: Any) -> FetchResult:
        timeout = kwargs.get("timeout", self.timeout)
        stealthy_headers = kwargs.get("stealthy_headers", self.stealthy_headers)

        def _do_fetch() -> FetchResult:
            try:
                from scrapling.fetchers import Fetcher
                resp = Fetcher.get(
                    url,
                    timeout=timeout,
                    stealthy_headers=stealthy_headers,
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
