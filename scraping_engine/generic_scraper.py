"""The fixed, generic scraping engine / interpreter.

Executes any SiteConfig against HTML or fetcher responses. Zero site-specific code.
"""

from typing import Any
from domain.site_config import SiteConfig, SelectorType
from domain.results import HealthReport, FieldHealth, SelectorStatus
from scraping_engine.selector_resolver import SelectorResolver
from scraping_engine.drift_aware_resolver import DriftAwareResolver


class GenericListScraper:
    """Fixed interpreter executing declarative SiteConfigs.

    Takes a SiteConfig and an HTML document/response, parses the job container items,
    resolves fields using DriftAwareResolver, and tracks health reports.
    """

    def __init__(self, resolver: SelectorResolver | None = None):
        self.resolver = resolver or DriftAwareResolver()

    def scrape_page(
        self,
        html_or_page: Any,
        config: SiteConfig,
    ) -> tuple[list[dict[str, Any]], HealthReport]:
        """Scrape raw record dictionaries and health metrics from a page document."""
        # Ensure page is wrapped in an Adaptor if it's raw HTML string
        page_doc = self._ensure_adaptor(html_or_page)

        # Locate listing containers
        containers = self._find_containers(page_doc, config)
        total_containers = len(containers)

        health_report = HealthReport(
            site_name=config.site_name,
            total_containers_found=total_containers,
        )

        if total_containers == 0:
            health_report.has_hard_failures = True
            health_report.details = f"Container selector '{config.container_selector}' matched 0 elements"
            return [], health_report

        records: list[dict[str, Any]] = []
        field_status_counts: dict[str, dict[SelectorStatus, int]] = {
            f.field_name: {s: 0 for s in SelectorStatus} for f in config.fields
        }
        field_samples: dict[str, str | None] = {}

        for container in containers:
            record: dict[str, Any] = {}
            for field_map in config.fields:
                res = self.resolver.resolve(container, field_map)
                record[field_map.field_name] = res.value
                field_status_counts[field_map.field_name][res.status] += 1
                if res.value and field_map.field_name not in field_samples:
                    field_samples[field_map.field_name] = res.value
            records.append(record)

        # Build field health summaries
        for field_map in config.fields:
            fname = field_map.field_name
            counts = field_status_counts[fname]

            # Determine dominant status
            if counts[SelectorStatus.MISSED] == total_containers:
                dominant_status = SelectorStatus.MISSED
            elif counts[SelectorStatus.AUTO_MATCHED] > 0:
                dominant_status = SelectorStatus.AUTO_MATCHED
            else:
                dominant_status = SelectorStatus.DIRECT_MATCH

            health_report.field_healths[fname] = FieldHealth(
                field_name=fname,
                status=dominant_status,
                sample_value=field_samples.get(fname),
            )

        health_report.evaluate()
        return records, health_report

    def _ensure_adaptor(self, html_or_page: Any) -> Any:
        if isinstance(html_or_page, str):
            try:
                from scrapling import Selector
                return Selector(html_or_page)
            except ImportError:
                return html_or_page
        return html_or_page

    def _find_containers(self, page_doc: Any, config: SiteConfig) -> list[Any]:
        try:
            if config.container_selector_type == SelectorType.CSS:
                if hasattr(page_doc, "css"):
                    return list(page_doc.css(config.container_selector))
            else:
                if hasattr(page_doc, "xpath"):
                    return list(page_doc.xpath(config.container_selector))
        except Exception:
            return []
        return []
