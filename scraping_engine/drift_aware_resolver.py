"""Drift-aware selector resolver utilizing Scrapling's adaptive relocation."""

from typing import Any
from domain.site_config import FieldMapping, SelectorType
from domain.results import SelectorStatus
from scraping_engine.selector_resolver import SelectorResolver, ResolveResult, ScraplingResolver


class DriftAwareResolver(SelectorResolver):
    """Wraps ScraplingResolver with a 2-stage fallback detection:
    
    1. Direct match (adaptive=False)
    2. If direct fails: adaptive relocation (adaptive=True or auto_match=True)
    3. If relocated: records soft failure (AUTO_MATCHED)
    4. If both fail: records hard failure (MISSED)
    """

    def __init__(self, base_resolver: ScraplingResolver | None = None):
        self.base_resolver = base_resolver or ScraplingResolver()

    def resolve(self, container_element: Any, mapping: FieldMapping) -> ResolveResult:
        # Phase 1: Direct match
        direct_result = self.base_resolver.resolve(container_element, mapping)
        if direct_result.status == SelectorStatus.DIRECT_MATCH:
            return direct_result

        # Phase 2: Adaptive relocation fallback
        # Try adaptive matching if supported on element
        try:
            relocated_elem = None
            identifier = f"{mapping.field_name}_{mapping.selector}"

            if mapping.selector_type == SelectorType.CSS and hasattr(container_element, "css"):
                try:
                    # Try modern Scrapling 'adaptive=True'
                    matches = container_element.css(mapping.selector, adaptive=True, identifier=identifier)
                    if matches:
                        relocated_elem = matches[0]
                except TypeError:
                    # Fallback to older 'auto_match=True' alias
                    matches = container_element.css(mapping.selector, auto_match=True, identifier=identifier)
                    if matches:
                        relocated_elem = matches[0]
            elif mapping.selector_type == SelectorType.XPATH and hasattr(container_element, "xpath"):
                try:
                    matches = container_element.xpath(mapping.selector, adaptive=True, identifier=identifier)
                    if matches:
                        relocated_elem = matches[0]
                except TypeError:
                    matches = container_element.xpath(mapping.selector, auto_match=True, identifier=identifier)
                    if matches:
                        relocated_elem = matches[0]

            if relocated_elem is not None:
                val = self.base_resolver._extract_value(relocated_elem, mapping)
                return ResolveResult(
                    field_name=mapping.field_name,
                    status=SelectorStatus.AUTO_MATCHED,
                    value=val,
                    raw_element=relocated_elem,
                )

        except Exception as e:
            # Relocation threw or was unsupported
            pass

        # Phase 3: Both direct match and auto-match failed -> Hard failure
        return ResolveResult(
            field_name=mapping.field_name,
            status=SelectorStatus.MISSED,
            value=mapping.default_value,
            error_message="Both direct selector and adaptive relocation failed",
        )
