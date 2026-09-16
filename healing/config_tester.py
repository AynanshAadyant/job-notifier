"""Sandbox tester evaluating candidate SiteConfigs against sample HTML before production adoption."""

from typing import Any
from domain.site_config import SiteConfig
from scraping_engine.generic_scraper import GenericListScraper
from validation.normalizer import RecordNormalizer
from validation.schema_validator import SchemaValidator


class ConfigTesterResult:
    def __init__(self, is_valid: bool, reason: str, sample_records: list[dict[str, Any]] | None = None):
        self.is_valid = is_valid
        self.reason = reason
        self.sample_records = sample_records or []


class ConfigTester:
    """Runs candidate config through the fixed engine on a held-out HTML sample to verify before trust."""

    def __init__(self, scraper: GenericListScraper | None = None):
        self.scraper = scraper or GenericListScraper()

    def test_config(self, candidate_config: SiteConfig, html_sample: str) -> ConfigTesterResult:
        # Step 1: Run through fixed scraper engine
        records, health_report = self.scraper.scrape_page(html_sample, candidate_config)

        if health_report.total_containers_found == 0:
            return ConfigTesterResult(
                is_valid=False,
                reason=f"Candidate container selector '{candidate_config.container_selector}' matched 0 elements",
            )

        if health_report.has_hard_failures:
            return ConfigTesterResult(
                is_valid=False,
                reason=f"Candidate config produced hard selector failures on test HTML",
                sample_records=records,
            )

        # Step 2: Normalize and validate records
        normalizer = RecordNormalizer(candidate_config.base_url, candidate_config.site_name)
        norm_records = [normalizer.normalize(r) for r in records]
        validator = SchemaValidator()
        val_result = validator.validate_all(norm_records)

        if len(val_result.valid_postings) == 0:
            return ConfigTesterResult(
                is_valid=False,
                reason="Candidate config generated 0 valid JobPostings after schema validation",
                sample_records=records,
            )

        # Step 3: Acceptance check passes
        return ConfigTesterResult(
            is_valid=True,
            reason=f"Sandbox test passed: {len(val_result.valid_postings)} valid listings extracted",
            sample_records=records[:3],
        )
