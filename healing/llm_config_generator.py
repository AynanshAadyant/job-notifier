"""Decoupled LLM-backed config generator using abstract LLMClient."""

import json
from domain.site_config import SiteConfig
from healing.config_generator import ConfigGenerator
from healing.ai_provider import LLMClient, LLMProviderFactory


class LLMConfigGenerator(ConfigGenerator):
    """Generates healed SiteConfig using any LLMClient conforming to the structured output contract.

    Central Safety Boundary:
    The LLM is prompted strictly to return a SiteConfig JSON structure.
    It cannot emit executable code, shell commands, or arbitrary scripts.
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        api_key: str | None = None,
        provider: str = "gemini",
        model_name: str | None = None,
        base_url: str | None = None,
    ):
        if llm_client is not None:
            self.llm_client = llm_client
        else:
            self.llm_client = LLMProviderFactory.create_client(
                provider=provider,
                api_key=api_key,
                model_name=model_name,
                base_url=base_url,
            )

    async def generate(
        self,
        html_sample: str,
        failure_context: str,
        current_config: SiteConfig,
    ) -> SiteConfig:
        # Construct prompt
        system_instruction = (
            "You are an expert web scraping engineer specializing in CSS and XPath selector extraction.\n"
            "Your task is to analyze the provided HTML sample from a job board and heal the broken SiteConfig.\n"
            "RULES:\n"
            "1. You MUST emit ONLY valid structured configuration adhering to the SiteConfig schema.\n"
            "2. NEVER emit Python code, scripts, or explanations outside the JSON schema.\n"
            "3. Ensure container_selector matches individual job item listing rows/cards.\n"
            "4. Required fields 'title', 'company', and 'url' must have working CSS/XPath selectors relative to container_selector.\n"
            "5. Increment the version number by 1."
        )

        current_config_dict = current_config.model_dump(mode="json")
        prompt = (
            f"=== CURRENT CONFIG ===\n"
            f"{json.dumps(current_config_dict, indent=2)}\n\n"
            f"=== FAILURE REASON ===\n"
            f"{failure_context}\n\n"
            f"=== HTML SAMPLE ===\n"
            f"{html_sample}\n\n"
            "Inspect the HTML carefully. Identify why the current selectors failed and provide the complete healed SiteConfig."
        )

        # Generate through abstracted client
        healed_config = await self.llm_client.generate_structured(
            prompt=prompt,
            response_schema=SiteConfig,
            system_instruction=system_instruction,
            temperature=0.1,
        )

        # Ensure version is monotonically incremented
        if healed_config.version <= current_config.version:
            healed_config.version = current_config.version + 1

        healed_config.healing_summary = f"Healed via {type(self.llm_client).__name__}: {failure_context}"
        return healed_config
