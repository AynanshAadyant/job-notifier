"""Unit tests for the model-agnostic AI provider abstraction."""

import pytest
from pydantic import BaseModel, Field

from domain.site_config import SiteConfig
from healing.ai_provider import (
    LLMClient,
    MockLLMClient,
    LLMProviderFactory,
    OpenAICompatibleLLMClient,
)
from healing.llm_config_generator import LLMConfigGenerator


class DummySchema(BaseModel):
    name: str = Field(default="test")
    score: int = Field(default=42)


@pytest.mark.asyncio
async def test_mock_llm_client_fixed_response():
    expected = DummySchema(name="healed", score=99)
    client = MockLLMClient(fixed_response=expected)

    result = await client.generate_structured(
        prompt="Heal this",
        response_schema=DummySchema,
    )
    assert result.name == "healed"
    assert result.score == 99


def test_llm_provider_factory_mock():
    client = LLMProviderFactory.create_client(provider="mock")
    assert isinstance(client, MockLLMClient)


def test_llm_provider_factory_ollama():
    client = LLMProviderFactory.create_client(
        provider="ollama",
        model_name="llama3",
        base_url="http://localhost:11434/v1",
    )
    assert isinstance(client, OpenAICompatibleLLMClient)
    assert client.model_name == "llama3"
    assert str(client.base_url).rstrip("/") == "http://localhost:11434/v1"


def test_llm_provider_factory_invalid_provider():
    with pytest.raises(ValueError, match="Unsupported AI provider"):
        LLMProviderFactory.create_client(provider="unsupported_vendor_123")


@pytest.mark.asyncio
async def test_llm_config_generator_with_abstract_client():
    # Build a sample SiteConfig
    base_config = SiteConfig(
        site_name="test_site",
        base_url="https://example.com",
        container_selector="tr.job",
        fields=[],
        version=1,
    )

    healed_target = SiteConfig(
        site_name="test_site",
        base_url="https://example.com",
        container_selector="div.healed_job",
        fields=[],
        version=1,
    )

    mock_client = MockLLMClient(fixed_response=healed_target)
    generator = LLMConfigGenerator(llm_client=mock_client)

    result = await generator.generate(
        html_sample="<div>test</div>",
        failure_context="Selector missed",
        current_config=base_config,
    )

    # Version should be monotonically incremented
    assert result.version == 2
    assert result.container_selector == "div.healed_job"
    assert "MockLLMClient" in (result.healing_summary or "")
