"""Pagination package exports."""

from scraping_engine.pagination.pagination_interface import PaginationHandler
from scraping_engine.pagination.pagination_factory import (
    NextLinkPagination,
    PageNumberPagination,
    InfiniteScrollPagination,
    PaginationFactory,
)

__all__ = [
    "PaginationHandler",
    "NextLinkPagination",
    "PageNumberPagination",
    "InfiniteScrollPagination",
    "PaginationFactory",
]
