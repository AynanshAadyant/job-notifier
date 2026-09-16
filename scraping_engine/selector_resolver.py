"""Selector resolver interface and Scrapling-backed implementation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
import re

from domain.site_config import FieldMapping, SelectorType, ExtractionType
from domain.results import SelectorStatus


@dataclass
class ResolveResult:
    """Outcome of resolving a single field selector on an element."""
    field_name: str
    status: SelectorStatus
    value: str | None = None
    raw_element: Any | None = None
    error_message: str | None = None


class SelectorResolver(ABC):
    """Abstract interface for extracting fields using selectors."""

    @abstractmethod
    def resolve(self, container_element: Any, mapping: FieldMapping) -> ResolveResult:
        """Extract value for mapping from container_element."""
        pass


class ScraplingResolver(SelectorResolver):
    """Concrete resolver using Scrapling's Adaptor API."""

    def resolve(self, container_element: Any, mapping: FieldMapping) -> ResolveResult:
        try:
            matched_elem = None
            if mapping.selector_type == SelectorType.CSS:
                # Scrapling's css_first or css list
                if hasattr(container_element, "css_first"):
                    matched_elem = container_element.css_first(mapping.selector)
                elif hasattr(container_element, "css"):
                    elems = container_element.css(mapping.selector)
                    matched_elem = elems[0] if elems else None
            else:
                if hasattr(container_element, "xpath_first"):
                    matched_elem = container_element.xpath_first(mapping.selector)
                elif hasattr(container_element, "xpath"):
                    elems = container_element.xpath(mapping.selector)
                    matched_elem = elems[0] if elems else None

            if matched_elem is None:
                return ResolveResult(
                    field_name=mapping.field_name,
                    status=SelectorStatus.MISSED,
                    value=mapping.default_value,
                )

            extracted_value = self._extract_value(matched_elem, mapping)
            if not extracted_value and mapping.default_value:
                extracted_value = mapping.default_value

            return ResolveResult(
                field_name=mapping.field_name,
                status=SelectorStatus.DIRECT_MATCH,
                value=extracted_value,
                raw_element=matched_elem,
            )

        except Exception as e:
            return ResolveResult(
                field_name=mapping.field_name,
                status=SelectorStatus.MISSED,
                value=mapping.default_value,
                error_message=str(e),
            )

    def _extract_value(self, element: Any, mapping: FieldMapping) -> str | None:
        raw_val = None
        if mapping.extraction == ExtractionType.CLEAN_TEXT:
            raw_val = getattr(element, "clean_text", None) or getattr(element, "text", "")
        elif mapping.extraction == ExtractionType.TEXT:
            raw_val = getattr(element, "text", "")
        elif mapping.extraction == ExtractionType.MARKDOWN:
            if hasattr(element, "markdown"):
                raw_val = element.markdown()
            else:
                raw_val = getattr(element, "text", "")
        elif mapping.extraction == ExtractionType.ATTRIBUTE:
            attr = mapping.attribute_name or "href"
            attribs = getattr(element, "attrib", {}) or getattr(element, "attributes", {})
            raw_val = attribs.get(attr)

        if raw_val is None:
            return None

        val_str = str(raw_val).strip()

        if mapping.regex_pattern:
            match = re.search(mapping.regex_pattern, val_str)
            if match:
                val_str = match.group(1) if match.groups() else match.group(0)
            else:
                val_str = ""

        return val_str
