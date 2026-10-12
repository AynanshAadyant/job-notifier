"""Self-Healing Job Scraper & Notifier Package."""

from bot import (
    JobNotifierBot,
    BotStatus,
    start_bot,
    run_once,
    create_bot,
)
from settings import Settings, settings
from domain.job_posting import JobPosting
from domain.site_config import SiteConfig, FieldMapping, PaginationRule
from domain.results import ScrapeResult, HealthReport, AnomalyReport, HealingEvent
from healing.ai_provider import (
    LLMClient,
    GeminiLLMClient,
    OpenAILLMClient,
    OpenAICompatibleLLMClient,
    MockLLMClient,
    LLMProviderFactory,
)

__all__ = [
    "JobNotifierBot",
    "BotStatus",
    "start_bot",
    "run_once",
    "create_bot",
    "Settings",
    "settings",
    "JobPosting",
    "SiteConfig",
    "FieldMapping",
    "PaginationRule",
    "ScrapeResult",
    "HealthReport",
    "AnomalyReport",
    "HealingEvent",
    "LLMClient",
    "GeminiLLMClient",
    "OpenAILLMClient",
    "OpenAICompatibleLLMClient",
    "MockLLMClient",
    "LLMProviderFactory",
]
