"""Unit tests for the anomaly detector."""

import pytest
from validation.anomaly_detector import AnomalyDetector
from domain.job_posting import JobPosting
from domain.results import AnomalyType


def test_anomaly_detector_zero_results():
    detector = AnomalyDetector()
    report = detector.detect(
        site_name="test_site",
        total_raw_records=0,
        valid_records=[],
        rejected_records=[],
    )
    assert report.is_anomalous
    assert AnomalyType.ZERO_RESULTS in report.anomalies


def test_anomaly_detector_high_rejection():
    detector = AnomalyDetector(max_rejection_rate=0.3)
    # 2 valid, 8 rejected -> 80% rejection
    valid = [JobPosting(title=f"T{i}", company="C", url=f"http://example.com/{i}", source_site="test") for i in range(2)]
    rejected = [({"title": ""}, "Missing title")] * 8

    report = detector.detect(
        site_name="test_site",
        total_raw_records=10,
        valid_records=valid,
        rejected_records=rejected,
    )
    assert report.is_anomalous
    assert AnomalyType.HIGH_REJECTION_RATE in report.anomalies


def test_anomaly_detector_degenerate_duplicates():
    detector = AnomalyDetector(max_duplicate_title_ratio=0.4)
    # 10 records with same title
    valid = [JobPosting(title="Identical Title", company="C", url=f"http://example.com/{i}", source_site="test") for i in range(10)]
    report = detector.detect(
        site_name="test_site",
        total_raw_records=10,
        valid_records=valid,
        rejected_records=[],
    )
    assert report.is_anomalous
    assert AnomalyType.DEGENERATE_DATA in report.anomalies
