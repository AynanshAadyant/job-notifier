"""LLM-backed config generator using Google Gemini with structured Pydantic schema output."""

import json
from google import genai
from google.genai import types

from domain.site_config import SiteConfig
from healing.config_generator import ConfigGenerator


class LLMConfigGenerator(ConfigGenerator):
    """Generates healed SiteConfig using Gemini with strict Pydantic JSON schema constraints.

    Central Safety Boundary:
    The LLM is prompted strictly to return a SiteConfig JSON structure.
    It cannot emit executable code, shell commands, or arbitrary scripts.
    """

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model_name = model_name
        self.client = genai.Client(api_key=api_key)

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

        # Call Gemini with structured output
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=SiteConfig,
                temperature=0.1,
            ),
        )

        raw_json = response.text
        if not raw_json:
            raise ValueError("Gemini returned empty response during config healing")

        # Parse and validate through Pydantic
        healed_data = json.loads(raw_json)
        healed_config = SiteConfig(**healed_data)

        # Ensure version is monotonically incremented
        if healed_config.version <= current_config.version:
            healed_config.version = current_config.version + 1

        healed_config.healing_summary = f"Healed by {self.model_name}: {failure_context}"
        return healed_config
