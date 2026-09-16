"""Abstract base class and contract for page fetchers.

The fetching layer is completely isolated from LLM influence.
Network, authentication, and stealth behavior are static.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class FetchResult:
    """Wrapper around raw network fetch outcome."""
    url: str
    status_code: int
    text: str
    headers: dict[str, str]
    is_success: bool
    error_message: str | None = None
    response_obj: Any | None = None  # Reference to underlying Scrapling Response if available


class PageFetcher(ABC):
    """Abstract interface for all page retrieval engines."""

    @abstractmethod
    async def fetch(self, url: str, **kwargs: Any) -> FetchResult:
        """Fetch page content for the given URL.

        Args:
            url: The HTTP(S) URL to retrieve.
            kwargs: Extra fetch arguments (headers, cookies, timeouts).

        Returns:
            FetchResult containing status and HTML body.
        """
        pass
