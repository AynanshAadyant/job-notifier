"""Unit tests for the GenericListScraper engine against HTML fixtures."""

import json
from pathlib import Path
import pytest

from domain.site_config import SiteConfig
from scraping_engine.generic_scraper import GenericListScraper
from validation.normalizer import RecordNormalizer
from validation.schema_validator import SchemaValidator

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
CONFIGS_DIR = Path(__file__).resolve().parent.parent.parent / "configs"


def test_generic_scraper_remoteok_fixture():
    # 1. Load config
    with open(CONFIGS_DIR / "remoteok.json", "r", encoding="utf-8") as f:
        config_data = json.load(f)
    config = SiteConfig(**config_data)

    # 2. Load fixture HTML
    with open(FIXTURES_DIR / "remoteok_sample.html", "r", encoding="utf-8") as f:
        html = f.read()

    # 3. Scrape
    scraper = GenericListScraper()
    raw_records, health = scraper.scrape_page(html, config)

    assert health.total_containers_found == 3
    assert not health.has_hard_failures
    assert len(raw_records) == 3

    # 4. Normalize & Validate
    normalizer = RecordNormalizer(config.base_url, config.site_name)
    normalized = [normalizer.normalize(r) for r in raw_records]
    validator = SchemaValidator()
    val_res = validator.validate_all(normalized)

    assert len(val_res.valid_postings) == 3
    assert len(val_res.rejected_records) == 0

    first_job = val_res.valid_postings[0]
    assert first_job.title == "Senior Python Engineer"
    assert first_job.company == "Acme Corp"
    assert first_job.url == "https://remoteok.com/remote-jobs/101-senior-python-engineer"
    assert first_job.location == "Remote, Worldwide"


def test_generic_scraper_broken_container():
    with open(CONFIGS_DIR / "remoteok.json", "r", encoding="utf-8") as f:
        config_data = json.load(f)
    config_data["container_selector"] = "div.non_existent_class"
    config = SiteConfig(**config_data)

    with open(FIXTURES_DIR / "remoteok_sample.html", "r", encoding="utf-8") as f:
        html = f.read()

    scraper = GenericListScraper()
    raw_records, health = scraper.scrape_page(html, config)

    assert health.total_containers_found == 0
    assert health.has_hard_failures
    assert len(raw_records) == 0
