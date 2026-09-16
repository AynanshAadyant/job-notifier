"""Per-site scrape pipeline runner: fetch -> scrape -> validate -> heal-if-needed -> persist."""

import time
import asyncio
from domain.site_config import SiteConfig, PaginationStrategy
from domain.job_posting import JobPosting
from domain.results import ScrapeResult, HealthReport, AnomalyReport
from fetching.fetcher_factory import FetcherFactory
from scraping_engine.generic_scraper import GenericListScraper
from scraping_engine.pagination.pagination_factory import PaginationFactory
from validation.normalizer import RecordNormalizer
from validation.schema_validator import SchemaValidator
from validation.anomaly_detector import AnomalyDetector
from healing.healing_trigger import HealingTrigger, CompositeHealingTrigger
from healing.healing_orchestrator import HealingOrchestrator
from persistence.config_repository_interface import ConfigRepository
from persistence.result_repository import ResultRepository
from observability.logging_config import get_logger
from observability.alerting import AlertService, LogAlertService

logger = get_logger(__name__)


class ScrapeJobRunner:
    """Coordinates the full execution pipeline for a single target site."""

    def __init__(
        self,
        config_repo: ConfigRepository,
        result_repo: ResultRepository,
        healing_orchestrator: HealingOrchestrator | None = None,
        healing_trigger: HealingTrigger | None = None,
        alert_service: AlertService | None = None,
        scraper: GenericListScraper | None = None,
    ):
        self.config_repo = config_repo
        self.result_repo = result_repo
        self.healing_orchestrator = healing_orchestrator
        self.healing_trigger = healing_trigger or CompositeHealingTrigger()
        self.alert_service = alert_service or LogAlertService()
        self.scraper = scraper or GenericListScraper()
        self.validator = SchemaValidator()
        self.anomaly_detector = AnomalyDetector()

    async def run(self, site_name: str) -> ScrapeResult:
        start_time = time.time()
        logger.info("Starting scrape job", site_name=site_name)

        # 1. Load active config
        config = await self.config_repo.get_active_config(site_name)
        if not config:
            err = f"No active config found for site '{site_name}'"
            logger.error(err)
            empty_health = HealthReport(site_name=site_name, total_containers_found=0, has_hard_failures=True)
            empty_anomaly = AnomalyReport(site_name=site_name, is_anomalous=True)
            return ScrapeResult(site_name=site_name, success=False, health_report=empty_health, anomaly_report=empty_anomaly, error=err)

        # 2. Initialize fetcher
        fetcher = FetcherFactory.get_fetcher(config.fetch_strategy)
        normalizer = RecordNormalizer(config.base_url, config.site_name)

        all_raw_records: list[dict] = []
        overall_health = HealthReport(site_name=site_name, total_containers_found=0)
        pages_scraped = 0
        current_url = config.base_url
        page_num = config.pagination.start_page
        last_html_sample = ""
        is_network_error = False

        # 3. Scrape loop across pagination
        pagination_handler = PaginationFactory.get_handler(config.pagination.strategy)

        while current_url and pages_scraped < config.pagination.max_pages:
            logger.debug("Fetching page", url=current_url, page_num=page_num)
            fetch_res = await fetcher.fetch(current_url)
            if not fetch_res.is_success:
                is_network_error = True
                logger.error("Fetch failed", url=current_url, status=fetch_res.status_code, error=fetch_res.error_message)
                break

            last_html_sample = fetch_res.text
            page_records, page_health = self.scraper.scrape_page(fetch_res.text, config)
            pages_scraped += 1
            all_raw_records.extend(page_records)
            overall_health = page_health

            # Delay before next page
            if config.crawl_delay_seconds > 0 and pages_scraped < config.pagination.max_pages:
                await asyncio.sleep(config.crawl_delay_seconds)

            if config.pagination.strategy == PaginationStrategy.NONE:
                break

            # Obtain next URL
            next_url = pagination_handler.get_next_page(
                page_doc=self.scraper._ensure_adaptor(fetch_res.text),
                current_url=current_url,
                current_page_num=page_num,
                rule=config.pagination,
            )
            if not next_url or next_url == current_url:
                break
            current_url = next_url
            page_num += 1

        # 4. Normalize and validate records
        normalized_records = [normalizer.normalize(r) for r in all_raw_records]
        deduped_records = normalizer.deduplicate(normalized_records)
        val_result = self.validator.validate_all(deduped_records)

        # 5. Check anomalies
        hist_avg = await self.result_repo.get_historical_avg(site_name)
        anomaly_report = self.anomaly_detector.detect(
            site_name=site_name,
            total_raw_records=len(all_raw_records),
            valid_records=val_result.valid_postings,
            rejected_records=val_result.rejected_records,
            historical_avg_count=hist_avg,
        )

        # 6. Evaluate healing triggers
        should_heal, heal_reason = self.healing_trigger.should_heal(
            health_report=overall_health,
            anomaly_report=anomaly_report,
            network_error=is_network_error,
        )

        if should_heal and self.healing_orchestrator and last_html_sample:
            logger.warn("Self-healing triggered", site=site_name, reason=heal_reason)
            healed_config, events = await self.healing_orchestrator.heal(
                html_sample=last_html_sample[:30000],
                failure_reason=heal_reason,
                current_config=config,
            )
            if healed_config:
                logger.info("Self-healing SUCCEEDED, promoting new config", version=healed_config.version)
                await self.config_repo.save_config(healed_config)
                # Re-run scrape once with new config
                return await self.run(site_name)
            else:
                logger.error("Self-healing EXHAUSTED, sending human alert")
                await self.alert_service.send_alert(
                    site_name=site_name,
                    message=f"Self-healing exhausted for {site_name}. Cause: {heal_reason}",
                    context={"events": [e.model_dump() for e in events]},
                )

        # 7. Persist result
        elapsed = time.time() - start_time
        result = ScrapeResult(
            site_name=site_name,
            success=not is_network_error and len(val_result.valid_postings) > 0,
            postings=val_result.valid_postings,
            health_report=overall_health,
            anomaly_report=anomaly_report,
            execution_time_seconds=elapsed,
            pages_scraped=pages_scraped,
            error="Network error" if is_network_error else None,
        )
        await self.result_repo.save_result(result)

        logger.info(
            "Completed scrape job",
            site_name=site_name,
            valid_jobs=len(val_result.valid_postings),
            rejected=len(val_result.rejected_records),
            duration=f"{elapsed:.2f}s",
        )
        return result
