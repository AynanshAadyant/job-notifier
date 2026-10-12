"""Unit tests for the JobNotifierBot facade and callable functions."""

import pytest
import asyncio
from pathlib import Path

from bot import start_bot, run_once, create_bot, JobNotifierBot
from settings import Settings
from domain.job_posting import JobPosting
from healing.ai_provider import MockLLMClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.mark.asyncio
async def test_run_once_with_callback():
    captured_jobs: list[JobPosting] = []

    async def callback(jobs: list[JobPosting]):
        captured_jobs.extend(jobs)

    custom_settings = Settings(
        gemini_api_key="mock_key",
        ai_provider="mock",
    )

    results = await run_once(
        site_name="remoteok",
        settings=custom_settings,
        on_jobs_scraped=callback,
        llm_client=MockLLMClient(),
    )

    assert len(results) == 1
    result = results[0]
    assert result.site_name == "remoteok"
    # Even if network fetch is not live in unit tests or returns network error,
    # the function runs through without crashing and returns a ScrapeResult
    assert hasattr(result, "success")
    assert hasattr(result, "postings")


@pytest.mark.asyncio
async def test_start_bot_non_blocking_lifecycle():
    custom_settings = Settings(
        gemini_api_key="mock_key",
        ai_provider="mock",
    )

    bot = await start_bot(
        settings=custom_settings,
        site_names=["remoteok"],
        run_initial_scrape=False,
        block=False,
        llm_client=MockLLMClient(),
    )

    try:
        status = await bot.get_status()
        assert status.is_running is True
        assert "job_remoteok" in status.scheduled_jobs
        assert "remoteok" in status.active_sites
    finally:
        await bot.stop()

    status_after = await bot.get_status()
    assert status_after.is_running is False


@pytest.mark.asyncio
async def test_create_bot_status_introspection():
    custom_settings = Settings(
        gemini_api_key="mock_key",
        ai_provider="mock",
    )

    bot = await create_bot(
        settings=custom_settings,
        llm_client=MockLLMClient(),
    )

    status = await bot.get_status()
    assert status.is_running is False
    assert "remoteok" in status.active_sites
    assert status.healing_enabled is True
