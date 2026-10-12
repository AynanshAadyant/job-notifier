"""Model-agnostic structured LLM client abstraction layer.

Allows the self-healing and scraping workflows to use any LLM provider
(Google Gemini, OpenAI, Ollama, Groq, DeepSeek, or Mock) without coupling
to any specific vendor SDK.
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Any
import json
import asyncio
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMClient(ABC):
    """Abstract base interface for structured output LLM generation."""

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        response_schema: type[T],
        system_instruction: str | None = None,
        temperature: float = 0.1,
    ) -> T:
        """Generate a structured response adhering strictly to the given Pydantic model schema.

        Args:
            prompt: User/context prompt.
            response_schema: Target Pydantic model class to validate output against.
            system_instruction: Optional system instruction.
            temperature: Sampling temperature (default 0.1 for deterministic config generation).

        Returns:
            An instance of response_schema.
        """
        pass


class GeminiLLMClient(LLMClient):
    """Google Gemini implementation using google-genai SDK."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model_name = model_name
        from google import genai
        self.client = genai.Client(api_key=api_key)

    async def generate_structured(
        self,
        prompt: str,
        response_schema: type[T],
        system_instruction: str | None = None,
        temperature: float = 0.1,
    ) -> T:
        from google.genai import types

        def _call_gemini() -> str:
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=temperature,
            )
            if system_instruction:
                config.system_instruction = system_instruction

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
            return response.text or ""

        raw_json = await asyncio.to_thread(_call_gemini)
        if not raw_json.strip():
            raise ValueError("Gemini returned empty text response")

        data = json.loads(raw_json)
        return response_schema.model_validate(data)


class OpenAILLMClient(LLMClient):
    """OpenAI implementation using native structured outputs via openai SDK."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gpt-4o-mini",
        base_url: str | None = None,
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def generate_structured(
        self,
        prompt: str,
        response_schema: type[T],
        system_instruction: str | None = None,
        temperature: float = 0.1,
    ) -> T:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        # Try native parsed response first
        try:
            completion = await self.client.beta.chat.completions.parse(
                model=self.model_name,
                messages=messages,
                response_format=response_schema,
                temperature=temperature,
            )
            parsed = completion.choices[0].message.parsed
            if parsed is not None:
                return parsed
        except Exception:
            pass

        # Fallback to json_object response format
        schema_prompt = (
            f"{prompt}\n\nRespond ONLY in valid JSON matching this schema:\n"
            f"{json.dumps(response_schema.model_json_schema(), indent=2)}"
        )
        if messages and messages[-1]["role"] == "user":
            messages[-1]["content"] = schema_prompt

        completion = await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=temperature,
        )
        raw_content = completion.choices[0].message.content or ""
        data = json.loads(raw_content)
        return response_schema.model_validate(data)


class OpenAICompatibleLLMClient(OpenAILLMClient):
    """Client for local/custom OpenAI-compatible endpoints (Ollama, Groq, DeepSeek, vLLM)."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        api_key: str | None = None,
        model_name: str = "llama3",
    ):
        super().__init__(
            api_key=api_key or "not-needed",
            model_name=model_name,
            base_url=base_url,
        )


class MockLLMClient(LLMClient):
    """Deterministic in-memory mock client for tests and offline runs."""

    def __init__(self, fixed_response: BaseModel | None = None):
        self.fixed_response = fixed_response

    async def generate_structured(
        self,
        prompt: str,
        response_schema: type[T],
        system_instruction: str | None = None,
        temperature: float = 0.1,
    ) -> T:
        if self.fixed_response is not None:
            if isinstance(self.fixed_response, response_schema):
                return self.fixed_response
            data = self.fixed_response.model_dump()
            return response_schema.model_validate(data)

        # Fallback: instantiate schema with empty/default fields if possible
        try:
            return response_schema()
        except Exception:
            raise ValueError(f"MockLLMClient requires a valid fixed_response for schema {response_schema}")


class LLMProviderFactory:
    """Factory to instantiate the appropriate LLMClient based on provider configuration."""

    @staticmethod
    def create_client(
        provider: str = "gemini",
        api_key: str | None = None,
        model_name: str | None = None,
        base_url: str | None = None,
    ) -> LLMClient:
        norm_provider = (provider or "gemini").strip().lower()

        if norm_provider == "gemini":
            if not api_key:
                raise ValueError("API key required for Gemini provider")
            model = model_name or "gemini-2.5-flash"
            return GeminiLLMClient(api_key=api_key, model_name=model)

        elif norm_provider == "openai":
            if not api_key:
                raise ValueError("API key required for OpenAI provider")
            model = model_name or "gpt-4o-mini"
            return OpenAILLMClient(api_key=api_key, model_name=model, base_url=base_url)

        elif norm_provider in ("openai_compatible", "ollama", "groq", "deepseek", "local"):
            url = base_url or ("http://localhost:11434/v1" if norm_provider == "ollama" else "https://api.groq.com/openai/v1")
            model = model_name or ("llama3" if norm_provider == "ollama" else "llama-3.3-70b-versatile")
            return OpenAICompatibleLLMClient(base_url=url, api_key=api_key, model_name=model)

        elif norm_provider == "mock":
            return MockLLMClient()

        else:
            raise ValueError(
                f"Unsupported AI provider '{provider}'. "
                f"Supported options: 'gemini', 'openai', 'openai_compatible', 'ollama', 'groq', 'deepseek', 'mock'"
            )
