"""Scheduler orchestrating recurring scrapes across multiple configured sites."""

import asyncio
from typing import Callable, Awaitable
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from orchestration.scrape_job_runner import ScrapeJobRunner
from persistence.config_repository_interface import ConfigRepository
from observability.logging_config import get_logger

logger = get_logger(__name__)


class ScrapeScheduler:
    """Manages scheduled periodic runs of ScrapeJobRunner across target sites."""

    def __init__(
        self,
        runner: ScrapeJobRunner,
        config_repo: ConfigRepository,
        default_interval_hours: int = 6,
        job_wrapper: Callable[[str], Awaitable[None]] | None = None,
    ):
        self.runner = runner
        self.config_repo = config_repo
        self.default_interval_hours = default_interval_hours
        self.job_wrapper = job_wrapper
        self.scheduler = AsyncIOScheduler()

    @property
    def is_running(self) -> bool:
        """Whether the APScheduler is currently running."""
        return self.scheduler.running

    def get_scheduled_job_ids(self) -> list[str]:
        """Return list of active scheduled job IDs."""
        return [job.id for job in self.scheduler.get_jobs()]

    def schedule_site(self, site_name: str, interval_hours: int | None = None) -> None:
        hours = interval_hours or self.default_interval_hours
        trigger = IntervalTrigger(hours=hours)

        async def _job():
            try:
                if self.job_wrapper:
                    await self.job_wrapper(site_name)
                else:
                    await self.runner.run(site_name)
            except Exception as e:
                logger.error("Error running scheduled job", site_name=site_name, error=str(e))

        self.scheduler.add_job(
            _job,
            trigger=trigger,
            id=f"job_{site_name}",
            replace_existing=True,
            name=f"Scrape {site_name}",
        )
        logger.info("Scheduled scrape job", site_name=site_name, interval_hours=hours)

    def start(self) -> None:
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started successfully")

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
