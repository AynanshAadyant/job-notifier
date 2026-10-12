"""Application settings loaded from environment variables / .env file."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


_PROJECT_ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """All configurable knobs for the job-scraper system.

    Values are read from environment variables first, then from the .env file
    located next to this module. Secrets should never be committed — only
    .env.example is tracked.
    """

    model_config = SettingsConfigDict(
        env_file=_PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Decoupled AI / LLM Configuration ---------------------------------- #
    ai_provider: str = Field(
        default="gemini",
        description="AI provider name: 'gemini', 'openai', 'openai_compatible', 'ollama', 'groq', or 'mock'",
    )
    ai_model: str | None = Field(
        default=None,
        description="Specific model identifier (e.g. 'gemini-2.5-flash', 'gpt-4o-mini', 'llama3')",
    )
    ai_api_key: str | None = Field(
        default=None,
        description="Universal API key for the configured AI provider",
    )
    ai_base_url: str | None = Field(
        default=None,
        description="Base URL for OpenAI-compatible endpoints (e.g. 'http://localhost:11434/v1' for Ollama)",
    )

    # Backward compatibility with existing configs
    gemini_api_key: str | None = Field(
        default=None,
        description="Google Gemini API key (fallback if ai_api_key is not set)",
    )

    @property
    def effective_api_key(self) -> str | None:
        """Return the active API key across provider configurations."""
        return self.ai_api_key or self.gemini_api_key

    # --- Scraping behaviour ------------------------------------------------ #
    scrape_interval_hours: int = Field(
        default=6,
        description="Hours between scheduled scrapes for each site",
    )
    max_healing_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Max LLM retry attempts per healing cycle before escalation",
    )
    html_sample_max_chars: int = Field(
        default=30_000,
        description="Truncate HTML samples sent to the LLM to this many characters",
    )
    default_request_timeout: int = Field(
        default=30,
        description="HTTP request timeout in seconds",
    )
    default_crawl_delay: float = Field(
        default=2.0,
        ge=0,
        description="Politeness delay between requests to the same site (seconds)",
    )

    # --- Observability ----------------------------------------------------- #
    log_level: str = Field(default="INFO", description="Root log level")
    alert_webhook_url: str | None = Field(
        default=None,
        description="Webhook URL for human-escalation alerts (Slack/Discord/etc.)",
    )

    # --- Proxy ------------------------------------------------------------- #
    proxy_url: str | None = Field(default=None, description="Optional HTTP proxy URL")

    # --- Derived paths (not from env) -------------------------------------- #
    @property
    def configs_dir(self) -> Path:
        return _PROJECT_ROOT / "configs"

    @property
    def output_dir(self) -> Path:
        return _PROJECT_ROOT / "output"


# Module-level default settings instance.
settings = Settings()
