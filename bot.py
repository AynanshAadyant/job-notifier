"""JobNotifierBot application service and public callable API.

This module provides the primary interface for embedding the scraping engine
into external backends (FastAPI, Flask, Django), scheduled tasks (Celery, Cron, Lambda),
or running as a standalone background daemon.
"""

import asyncio
from datetime import datetime, timezone
from typing import Callable, Awaitable, Any
from pydantic import BaseModel, Field

from settings import Settings, settings as global_settings
from domain.job_posting import JobPosting
from domain.results import ScrapeResult
from persistence.config_repository_interface import ConfigRepository
from persistence.file_config_repository import FileConfigRepository
from persistence.result_repository import ResultRepository
from healing.ai_provider import LLMClient, LLMProviderFactory
from healing.llm_config_generator import LLMConfigGenerator
from healing.healing_orchestrator import HealingOrchestrator
from healing.healing_trigger import CompositeHealingTrigger, HealingTrigger
from observability.alerting import (
    AlertService,
    LogAlertService,
    WebhookAlertService,
    CompositeAlertService,
)
from observability.logging_config import setup_logging, get_logger
from orchestration.scrape_job_runner import ScrapeJobRunner
from orchestration.scheduler import ScrapeScheduler

logger = get_logger("bot")

JobCallback = Callable[[list[JobPosting]], Awaitable[None]]


class BotStatus(BaseModel):
    """Runtime status snapshot of the bot for monitoring and health check endpoints."""

    is_running: bool = Field(description="Whether the background scheduler is currently active")
    active_sites: list[str] = Field(default_factory=list, description="Registered site configurations")
    scheduled_jobs: list[str] = Field(default_factory=list, description="IDs of currently scheduled tasks")
    last_run_timestamp: dict[str, str] = Field(
        default_factory=dict,
        description="ISO timestamps of last execution per site",
    )
    ai_provider: str | None = Field(default=None, description="Active AI provider used for self-healing")
    healing_enabled: bool = Field(default=False, description="Whether LLM self-healing is active")


class JobNotifierBot:
    """Central bot coordinator managing lifecycle, scheduling, scraping, and callbacks.

    Designed for dependency injection and lifecycle management in external applications.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        config_repo: ConfigRepository | None = None,
        result_repo: ResultRepository | None = None,
        alert_service: AlertService | None = None,
        healing_orchestrator: HealingOrchestrator | None = None,
        llm_client: LLMClient | None = None,
        on_jobs_scraped: JobCallback | None = None,
    ):
        self.settings = settings or global_settings
        self.config_repo = config_repo or FileConfigRepository(self.settings.configs_dir)
        self.result_repo = result_repo or ResultRepository(self.settings.output_dir)
        self.alert_service = alert_service or self._build_default_alert_service()
        self.llm_client = llm_client
        self.healing_orchestrator = healing_orchestrator

        self._callbacks: list[JobCallback] = []
        if on_jobs_scraped:
            self._callbacks.append(on_jobs_scraped)

        self._last_run_timestamp: dict[str, str] = {}
        self._is_initialized = False
        self._is_running = False
        self.runner: ScrapeJobRunner | None = None
        self.scheduler: ScrapeScheduler | None = None

    def _build_default_alert_service(self) -> AlertService:
        services: list[AlertService] = [LogAlertService()]
        if self.settings.alert_webhook_url:
            services.append(WebhookAlertService(self.settings.alert_webhook_url))
        return CompositeAlertService(services) if len(services) > 1 else services[0]

    async def initialize(self) -> None:
        """Initialize repositories, AI providers, runner, and scheduler."""
        if self._is_initialized:
            return

        setup_logging(self.settings.log_level)

        # Initialize AI client and healing orchestrator if configured and not injected
        if self.healing_orchestrator is None:
            active_key = self.settings.effective_api_key
            provider = self.settings.ai_provider

            if self.llm_client is not None:
                generator = LLMConfigGenerator(llm_client=self.llm_client)
                self.healing_orchestrator = HealingOrchestrator(
                    generator=generator,
                    max_attempts=self.settings.max_healing_attempts,
                )
                logger.info("Initialized self-healing with injected LLMClient", client_type=type(self.llm_client).__name__)
            elif (active_key and active_key != "your-api-key-here") or provider == "mock" or provider in ("openai_compatible", "ollama"):
                try:
                    client = LLMProviderFactory.create_client(
                        provider=provider,
                        api_key=active_key,
                        model_name=self.settings.ai_model,
                        base_url=self.settings.ai_base_url,
                    )
                    generator = LLMConfigGenerator(llm_client=client)
                    self.healing_orchestrator = HealingOrchestrator(
                        generator=generator,
                        max_attempts=self.settings.max_healing_attempts,
                    )
                    logger.info("Initialized self-healing LLM provider", provider=provider, model=self.settings.ai_model)
                except Exception as e:
                    logger.warn("Failed to initialize AI provider; self-healing disabled", error=str(e), provider=provider)
            else:
                logger.info("No AI API key or mock provider configured; self-healing disabled")

        # Build runner
        self.runner = ScrapeJobRunner(
            config_repo=self.config_repo,
            result_repo=self.result_repo,
            healing_orchestrator=self.healing_orchestrator,
            healing_trigger=CompositeHealingTrigger(),
            alert_service=self.alert_service,
        )

        # Build scheduler with wrapper to invoke registered callbacks
        self.scheduler = ScrapeScheduler(
            runner=self.runner,
            config_repo=self.config_repo,
            default_interval_hours=self.settings.scrape_interval_hours,
            job_wrapper=self._scheduled_run_wrapper,
        )

        self._is_initialized = True
        logger.info("JobNotifierBot initialized successfully")

    async def _scheduled_run_wrapper(self, site_name: str) -> None:
        """Internal wrapper invoked by scheduler to ensure callbacks fire."""
        await self.run_site(site_name)

    def add_callback(self, callback: JobCallback) -> None:
        """Register a callback invoked whenever new valid job postings are scraped."""
        self._callbacks.append(callback)

    async def run_site(self, site_name: str) -> ScrapeResult:
        """Run scraping for a single site and trigger registered callbacks.

        Args:
            site_name: Identifier of the site to scrape.

        Returns:
            ScrapeResult containing postings, health, and anomalies.
        """
        if not self._is_initialized:
            await self.initialize()

        assert self.runner is not None
        result = await self.runner.run(site_name)
        self._last_run_timestamp[site_name] = datetime.now(timezone.utc).isoformat()

        # Fire callbacks if postings were collected
        if result.postings and self._callbacks:
            for cb in self._callbacks:
                try:
                    await cb(result.postings)
                except Exception as e:
                    logger.error("Error executing job callback", site_name=site_name, error=str(e))

        return result

    async def run_all(self, site_names: list[str] | None = None) -> list[ScrapeResult]:
        """Run scraping across all configured sites (or a specified subset).

        Args:
            site_names: Optional explicit list of sites to run. Defaults to all active sites.

        Returns:
            List of ScrapeResult objects.
        """
        if not self._is_initialized:
            await self.initialize()

        sites = site_names or await self.config_repo.list_sites()
        results: list[ScrapeResult] = []
        for site in sites:
            res = await self.run_site(site)
            results.append(res)
        return results

    async def start(
        self,
        block: bool = False,
        run_initial_scrape: bool = True,
        site_names: list[str] | None = None,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        """Start the bot and its background scheduler.

        Args:
            block: If True, blocks asynchronously until stop_event is set or process exits.
                   If False, returns immediately with scheduler running in background.
            run_initial_scrape: Whether to execute an immediate scrape across sites on startup.
            site_names: Optional subset of sites to schedule. Defaults to all discovered sites.
            stop_event: Optional asyncio.Event to trigger graceful shutdown when running blocked.
        """
        if not self._is_initialized:
            await self.initialize()

        assert self.scheduler is not None
        sites = site_names or await self.config_repo.list_sites()

        for site in sites:
            self.scheduler.schedule_site(site)

        if run_initial_scrape:
            logger.info("Executing initial scrape across active sites", sites=sites)
            await self.run_all(sites)

        self.scheduler.start()
        self._is_running = True
        logger.info("Bot started background scheduler", sites=sites)

        if block:
            event = stop_event or asyncio.Event()
            try:
                await event.wait()
            except (asyncio.CancelledError, KeyboardInterrupt):
                pass
            finally:
                await self.stop()

    async def stop(self) -> None:
        """Gracefully stop the background scheduler and bot operations."""
        if self.scheduler and self.scheduler.is_running:
            self.scheduler.shutdown()
        self._is_running = False
        logger.info("Bot stopped successfully")

    async def get_status(self) -> BotStatus:
        """Get the current operational status of the bot."""
        active_sites = await self.config_repo.list_sites() if self.config_repo else []
        scheduled_jobs = self.scheduler.get_scheduled_job_ids() if self.scheduler else []

        return BotStatus(
            is_running=self._is_running and (self.scheduler.is_running if self.scheduler else False),
            active_sites=active_sites,
            scheduled_jobs=scheduled_jobs,
            last_run_timestamp=self._last_run_timestamp,
            ai_provider=self.settings.ai_provider,
            healing_enabled=self.healing_orchestrator is not None,
        )


# --- Convenient Public Functions for External Callers --------------------- #

async def create_bot(
    settings: Settings | None = None,
    config_repo: ConfigRepository | None = None,
    result_repo: ResultRepository | None = None,
    alert_service: AlertService | None = None,
    llm_client: LLMClient | None = None,
    on_jobs_scraped: JobCallback | None = None,
) -> JobNotifierBot:
    """Create and initialize a JobNotifierBot instance."""
    bot = JobNotifierBot(
        settings=settings,
        config_repo=config_repo,
        result_repo=result_repo,
        alert_service=alert_service,
        llm_client=llm_client,
        on_jobs_scraped=on_jobs_scraped,
    )
    await bot.initialize()
    return bot


async def start_bot(
    settings: Settings | None = None,
    site_names: list[str] | None = None,
    run_initial_scrape: bool = True,
    block: bool = False,
    stop_event: asyncio.Event | None = None,
    on_jobs_scraped: JobCallback | None = None,
    llm_client: LLMClient | None = None,
) -> JobNotifierBot:
    """Start the job notifier bot workflow.

    Can be called directly from backends (FastAPI lifespan, Flask background task),
    cron runners, or scripts.

    Args:
        settings: Optional custom Settings instance.
        site_names: Optional specific list of sites to run. Defaults to all active configs.
        run_initial_scrape: Whether to scrape immediately on start.
        block: If False (default for backends), returns the active bot immediately while
               scheduler runs in background. If True, blocks until stopped.
        stop_event: Optional asyncio.Event for graceful shutdown in blocking mode.
        on_jobs_scraped: Optional async callback invoked with new JobPosting batches.
        llm_client: Optional injected LLMClient instance.

    Returns:
        The running JobNotifierBot instance.
    """
    bot = await create_bot(
        settings=settings,
        llm_client=llm_client,
        on_jobs_scraped=on_jobs_scraped,
    )
    await bot.start(
        block=block,
        run_initial_scrape=run_initial_scrape,
        site_names=site_names,
        stop_event=stop_event,
    )
    return bot


async def run_once(
    site_name: str | None = None,
    settings: Settings | None = None,
    on_jobs_scraped: JobCallback | None = None,
    llm_client: LLMClient | None = None,
) -> list[ScrapeResult]:
    """Execute a single-pass scrape for one or all sites and return results.

    Ideal for serverless execution (AWS Lambda, Google Cloud Functions), Celery tasks,
    or simple cron jobs.

    Args:
        site_name: Specific site to scrape, or None to scrape all configured sites.
        settings: Optional custom Settings instance.
        on_jobs_scraped: Optional async callback invoked when jobs are scraped.
        llm_client: Optional injected LLMClient.

    Returns:
        List of ScrapeResult objects containing jobs, health reports, and anomalies.
    """
    bot = await create_bot(
        settings=settings,
        llm_client=llm_client,
        on_jobs_scraped=on_jobs_scraped,
    )
    if site_name:
        result = await bot.run_site(site_name)
        return [result]
    return await bot.run_all()
