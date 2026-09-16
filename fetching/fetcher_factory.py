"""Factory mapping FetchStrategy enum to concrete PageFetcher instances."""

from domain.site_config import FetchStrategy
from fetching.fetcher_interface import PageFetcher
from fetching.http_fetcher import HttpFetcher
from fetching.stealth_fetcher import StealthFetcher
from fetching.dynamic_fetcher import DynamicFetcher


class FetcherFactory:
    """Factory to instantiate the appropriate PageFetcher based on SiteConfig strategy."""

    @staticmethod
    def get_fetcher(strategy: FetchStrategy, **kwargs) -> PageFetcher:
        if strategy == FetchStrategy.STATIC:
            return HttpFetcher(**kwargs)
        elif strategy == FetchStrategy.STEALTH:
            return StealthFetcher(**kwargs)
        elif strategy == FetchStrategy.DYNAMIC:
            return DynamicFetcher(**kwargs)
        else:
            return HttpFetcher(**kwargs)
