"""Pagination interface for multi-page extraction."""

from abc import ABC, abstractmethod
from typing import Any
from domain.site_config import PaginationRule


class PaginationHandler(ABC):
    """Abstract interface for determining next page URLs or dynamic actions."""

    @abstractmethod
    def get_next_page(
        self,
        page_doc: Any,
        current_url: str,
        current_page_num: int,
        rule: PaginationRule,
    ) -> str | None:
        """Return next absolute/relative URL string, or None if reached the end."""
        pass
