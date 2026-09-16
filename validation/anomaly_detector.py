"""Anomaly detector inspecting output batches for subtle extraction degradation."""

from typing import Any
from domain.results import AnomalyReport, AnomalyType


class AnomalyDetector:
    """Detects suspicious anomalies such as zero results, degenerate duplication, or high rejection rates."""

    def __init__(
        self,
        max_rejection_rate: float = 0.4,
        max_duplicate_title_ratio: float = 0.5,
        min_expected_records: int = 1,
    ):
        self.max_rejection_rate = max_rejection_rate
        self.max_duplicate_title_ratio = max_duplicate_title_ratio
        self.min_expected_records = min_expected_records

    def detect(
        self,
        site_name: str,
        total_raw_records: int,
        valid_records: list[Any],
        rejected_records: list[Any],
        historical_avg_count: float | None = None,
    ) -> AnomalyReport:
        report = AnomalyReport(
            site_name=site_name,
            total_raw_records=total_raw_records,
            valid_records_count=len(valid_records),
            rejected_records_count=len(rejected_records),
        )

        # 1. Zero results check
        if len(valid_records) == 0:
            report.is_anomalous = True
            report.anomalies.append(AnomalyType.ZERO_RESULTS)
            report.reasons.append("Scrape yielded zero valid job postings")
            return report

        # 2. High rejection rate check
        rejection_rate = len(rejected_records) / total_raw_records if total_raw_records > 0 else 0
        if rejection_rate > self.max_rejection_rate:
            report.is_anomalous = True
            report.anomalies.append(AnomalyType.HIGH_REJECTION_RATE)
            report.reasons.append(
                f"High rejection rate: {rejection_rate:.1%} exceeds threshold of {self.max_rejection_rate:.1%}"
            )

        # 3. Degenerate duplicate titles check
        titles = [getattr(r, "title", "") for r in valid_records if getattr(r, "title", None)]
        if len(titles) > 3:
            unique_titles = set(titles)
            dup_ratio = 1.0 - (len(unique_titles) / len(titles))
            if dup_ratio > self.max_duplicate_title_ratio:
                report.is_anomalous = True
                report.anomalies.append(AnomalyType.DEGENERATE_DATA)
                report.reasons.append(
                    f"Degenerate duplicate titles: {dup_ratio:.1%} duplicate ratio exceeds {self.max_duplicate_title_ratio:.1%}"
                )

        # 4. Volume drop check against historical baseline
        if historical_avg_count and historical_avg_count >= 5:
            if len(valid_records) < (historical_avg_count * 0.4):
                report.is_anomalous = True
                report.anomalies.append(AnomalyType.VOLUME_DROP)
                report.reasons.append(
                    f"Volume drop: Scraped {len(valid_records)} records, significantly below historical avg of {historical_avg_count:.1f}"
                )

        return report
