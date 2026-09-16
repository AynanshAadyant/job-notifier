"""Pagination handlers for next-link, page-number, and infinite-scroll."""

from typing import Any
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
from domain.site_config import PaginationRule, PaginationStrategy
from scraping_engine.pagination.pagination_interface import PaginationHandler


class NextLinkPagination(PaginationHandler):
    """Extracts next page URL from a 'Next' anchor tag."""

    def get_next_page(
        self,
        page_doc: Any,
        current_url: str,
        current_page_num: int,
        rule: PaginationRule,
    ) -> str | None:
        if current_page_num >= rule.max_pages:
            return None

        if not rule.next_link_selector:
            return None

        # Look for the next link element in the page document
        link_elem = None
        if hasattr(page_doc, "css_first"):
            link_elem = page_doc.css_first(rule.next_link_selector)
        elif hasattr(page_doc, "css"):
            elems = page_doc.css(rule.next_link_selector)
            link_elem = elems[0] if elems else None

        if not link_elem:
            return None

        attribs = getattr(link_elem, "attrib", {}) or getattr(link_elem, "attributes", {})
        href = attribs.get(rule.next_link_attribute or "href")
        if not href:
            return None

        return urljoin(current_url, href)


class PageNumberPagination(PaginationHandler):
    """Calculates next page URL using a template or query parameter."""

    def get_next_page(
        self,
        page_doc: Any,
        current_url: str,
        current_page_num: int,
        rule: PaginationRule,
    ) -> str | None:
        next_page = current_page_num + 1
        if next_page > rule.max_pages:
            return None

        if rule.url_template and "{page}" in rule.url_template:
            return rule.url_template.format(page=next_page)

        parsed = urlparse(current_url)
        params = parse_qs(parsed.query)
        params[rule.page_param] = [str(next_page)]
        new_query = urlencode(params, doseq=True)
        return urlunparse(parsed._replace(query=new_query))


class InfiniteScrollPagination(PaginationHandler):
    """Placeholder handler for scroll pagination (handled via DynamicFetcher actions)."""

    def get_next_page(
        self,
        page_doc: Any,
        current_url: str,
        current_page_num: int,
        rule: PaginationRule,
    ) -> str | None:
        # For infinite scroll, single-page dynamic fetch handles multi-scroll via browser actions
        return None


class PaginationFactory:
    """Factory to instantiate PaginationHandler based on strategy."""

    @staticmethod
    def get_handler(strategy: PaginationStrategy) -> PaginationHandler:
        if strategy == PaginationStrategy.NEXT_LINK:
            return NextLinkPagination()
        elif strategy == PaginationStrategy.PAGE_NUMBER:
            return PageNumberPagination()
        elif strategy == PaginationStrategy.INFINITE_SCROLL:
            return InfiniteScrollPagination()
        else:
            return PageNumberPagination()
