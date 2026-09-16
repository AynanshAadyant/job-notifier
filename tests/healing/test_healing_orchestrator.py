"""Unit tests for the healing orchestrator with mocked LLM generation."""

import pytest
import json
from pathlib import Path

from domain.site_config import SiteConfig
from healing.config_generator import ConfigGenerator
from healing.healing_orchestrator import HealingOrchestrator

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
CONFIGS_DIR = Path(__file__).resolve().parent.parent.parent / "configs"


class MockConfigGenerator(ConfigGenerator):
    """Mock generator returning predetermined healed config."""

    def __init__(self, succeed: bool = True):
        self.succeed = succeed

    async def generate(self, html_sample: str, failure_context: str, current_config: SiteConfig) -> SiteConfig:
        config_dict = current_config.model_dump()
        if self.succeed:
            # Fix broken selectors
            config_dict["container_selector"] = "tr.job"
            config_dict["version"] = current_config.version + 1
        else:
            # Continue returning broken selector
            config_dict["container_selector"] = "div.still_broken"
            config_dict["version"] = current_config.version + 1
        return SiteConfig(**config_dict)


@pytest.mark.asyncio
async def test_healing_orchestrator_success():
    with open(CONFIGS_DIR / "remoteok.json", "r", encoding="utf-8") as f:
        config_data = json.load(f)
    # Simulate broken config
    config_data["container_selector"] = "tr.broken"
    broken_config = SiteConfig(**config_data)

    with open(FIXTURES_DIR / "remoteok_sample.html", "r", encoding="utf-8") as f:
        html = f.read()

    generator = MockConfigGenerator(succeed=True)
    orchestrator = HealingOrchestrator(generator=generator, max_attempts=2)

    healed_config, events = await orchestrator.heal(
        html_sample=html,
        failure_reason="Container selector missed 0 elements",
        current_config=broken_config,
    )

    assert healed_config is not None
    assert healed_config.version == 2
    assert healed_config.container_selector == "tr.job"
    assert len(events) == 1
    assert events[0].passed_sandbox is True


@pytest.mark.asyncio
async def test_healing_orchestrator_exhaustion():
    with open(CONFIGS_DIR / "remoteok.json", "r", encoding="utf-8") as f:
        config_data = json.load(f)
    config_data["container_selector"] = "tr.broken"
    broken_config = SiteConfig(**config_data)

    with open(FIXTURES_DIR / "remoteok_sample.html", "r", encoding="utf-8") as f:
        html = f.read()

    generator = MockConfigGenerator(succeed=False)
    orchestrator = HealingOrchestrator(generator=generator, max_attempts=2)

    healed_config, events = await orchestrator.heal(
        html_sample=html,
        failure_reason="Container selector missed 0 elements",
        current_config=broken_config,
    )

    assert healed_config is None
    # 2 failed attempts + 1 final escalation event = 3 events
    assert len(events) == 3
    assert "Human escalation required" in events[-1].details
