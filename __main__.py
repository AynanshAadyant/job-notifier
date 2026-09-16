"""Entry point for the job scraper application."""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

from settings import settings
from observability.logging_config import setup_logging, get_logger
from persistence.file_config_repository import FileConfigRepository
from persistence.result_repository import ResultRepository
from healing.llm_config_generator import LLMConfigGenerator
from healing.healing_orchestrator import HealingOrchestrator
from healing.healing_trigger import CompositeHealingTrigger
from observability.alerting import WebhookAlertService, LogAlertService, CompositeAlertService
from orchestration.scrape_job_runner import ScrapeJobRunner
from orchestration.scheduler import ScrapeScheduler

load_dotenv()


async def main():
    setup_logging(settings.log_level)
    logger = get_logger("main")
    logger.info("Starting Self-Healing Job Scraper engine", env=os.getenv("ENV", "development"))

    # Repositories
    config_repo = FileConfigRepository(settings.configs_dir)
    result_repo = ResultRepository(settings.output_dir)

    # Observability & Alerting
    alert_services = [LogAlertService()]
    if settings.alert_webhook_url:
        alert_services.append(WebhookAlertService(settings.alert_webhook_url))
    alert_service = CompositeAlertService(alert_services)

    # Healing Orchestrator (if GEMINI_API_KEY is configured)
    healing_orchestrator = None
    if settings.gemini_api_key and settings.gemini_api_key != "your-gemini-api-key-here":
        generator = LLMConfigGenerator(api_key=settings.gemini_api_key)
        healing_orchestrator = HealingOrchestrator(
            generator=generator,
            max_attempts=settings.max_healing_attempts,
        )
        logger.info("LLM self-healing enabled with Gemini provider")
    else:
        logger.warn("GEMINI_API_KEY not provided; self-healing LLM disabled")

    # Scrape Job Runner
    runner = ScrapeJobRunner(
        config_repo=config_repo,
        result_repo=result_repo,
        healing_orchestrator=healing_orchestrator,
        healing_trigger=CompositeHealingTrigger(),
        alert_service=alert_service,
    )

    # Scheduler
    scheduler = ScrapeScheduler(
        runner=runner,
        config_repo=config_repo,
        default_interval_hours=settings.scrape_interval_hours,
    )

    # Discover and schedule all site configs
    configs = list(settings.configs_dir.glob("*.json"))
    for cfg_file in configs:
        if ".v" not in cfg_file.name:  # Exclude versioned archives
            site_name = cfg_file.stem
            scheduler.schedule_site(site_name)
            # Run immediate initial scrape
            logger.info("Executing initial scrape", site_name=site_name)
            await runner.run(site_name)

    scheduler.start()

    # Keep event loop running
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Application shutdown cleanly")


if __name__ == "__main__":
    asyncio.run(main())
