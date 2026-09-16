from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

from domain.job_posting import JobPosting


class SelectorStatus(str, Enum):
    DIRECT_MATCH = "direct_match"
    AUTO_MATCHED = "auto_matched"  # Soft failure: element relocated via adaptive matching
    MISSED = "missed"              # Hard failure: element not found even with auto-match


class FieldHealth(BaseModel):
    """Health status for a single field extraction."""

    field_name: str
    status: SelectorStatus
    sample_value: str | None = None
    similarity_score: float | None = None
    error_message: str | None = None


class HealthReport(BaseModel):
    """Overall selector health diagnostic from a scrape run."""

    site_name: str
    total_containers_found: int
    field_healths: dict[str, FieldHealth] = Field(default_factory=dict)
    has_hard_failures: bool = False
    has_soft_failures: bool = False
    details: str = ""

    def evaluate(self) -> None:
        """Derive overall failure flags from individual field reports."""
        self.has_hard_failures = any(
            fh.status == SelectorStatus.MISSED for fh in self.field_healths.values()
        )
        self.has_soft_failures = any(
            fh.status == SelectorStatus.AUTO_MATCHED for fh in self.field_healths.values()
        )


class AnomalyType(str, Enum):
    ZERO_RESULTS = "zero_results"
    VOLUME_DROP = "volume_drop"
    DEGENERATE_DATA = "degenerate_data"
    HIGH_REJECTION_RATE = "high_rejection_rate"


class AnomalyReport(BaseModel):
    """Anomalies detected in scraped payload even if schema validation passed."""

    site_name: str
    is_anomalous: bool = False
    anomalies: list[AnomalyType] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    total_raw_records: int = 0
    valid_records_count: int = 0
    rejected_records_count: int = 0


class ScrapeResult(BaseModel):
    """Comprehensive result of running a scrape job on a site."""

    site_name: str
    success: bool
    postings: list[JobPosting] = Field(default_factory=list)
    health_report: HealthReport
    anomaly_report: AnomalyReport
    execution_time_seconds: float = 0.0
    pages_scraped: int = 0
    error: str | None = None


class HealingEvent(BaseModel):
    """Audit log of a self-healing iteration."""

    site_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    old_version: int
    new_version: int | None = None
    trigger_reason: str
    passed_sandbox: bool = False
    details: str = ""
    candidate_config_json: str | None = None
