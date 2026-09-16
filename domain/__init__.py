"""Domain package exports."""

from domain.site_config import (
    SiteConfig,
    FieldMapping,
    PaginationRule,
    SelectorType,
    ExtractionType,
    FetchStrategy,
    PaginationStrategy,
)
from domain.job_posting import JobPosting
from domain.results import (
    ScrapeResult,
    HealthReport,
    FieldHealth,
    SelectorStatus,
    AnomalyReport,
    AnomalyType,
    HealingEvent,
)

__all__ = [
    "SiteConfig",
    "FieldMapping",
    "PaginationRule",
    "SelectorType",
    "ExtractionType",
    "FetchStrategy",
    "PaginationStrategy",
    "JobPosting",
    "ScrapeResult",
    "HealthReport",
    "FieldHealth",
    "SelectorStatus",
    "AnomalyReport",
    "AnomalyType",
    "HealingEvent",
]
