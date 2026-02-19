"""LLM Service for External API Integration.

Provides a unified interface for interacting with multiple LLM providers:
- OpenAI (GPT-4, GPT-3.5)
- Anthropic Claude (Claude 3, Claude 2)

Features:
- Abstract interface for text generation
- Provider selection via configuration
- Rate limiting and retry logic
- Token counting and cost estimation
- Singleton pattern for efficient resource usage
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Data Classes
# ============================================================================


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    XAI = "xai"
    OLLAMA = "ollama"


class LLMModel(str, Enum):
    """Supported LLM models."""

    # OpenAI models
    GPT52 = "gpt-5.2"
    GPT52_PRO = "gpt-5.2-pro"
    GPT52_INSTANT = "gpt-5.2-chat-latest"
    GPT5_CODEX = "gpt-5-codex"
    GPT4O = "gpt-4o"
    GPT4O_MINI = "gpt-4o-mini"

    # Anthropic models
    CLAUDE_OPUS_4_6 = "claude-opus-4-6"
    CLAUDE_SONNET_4_5 = "claude-sonnet-4-5-20250929"
    CLAUDE_HAIKU_4_5 = "claude-haiku-4-5-20251001"

    # Google models
    GEMINI_3_PRO = "gemini-3-pro-preview"
    GEMINI_3_FLASH = "gemini-3-flash-preview"
    GEMINI_25_PRO = "gemini-2.5-pro"
    GEMINI_25_FLASH = "gemini-2.5-flash"

    # xAI models
    GROK_41_FAST = "grok-4-1-fast-reasoning"
    GROK_4 = "grok-4-0709"
    GROK_3 = "grok-3"


@dataclass
class LLMConfig:
    """Configuration for LLM service."""

    provider: LLMProvider = LLMProvider.ANTHROPIC
    model: str = "claude-opus-4-6"
    max_tokens: int = 4096
    temperature: float = 0.3
    timeout_seconds: int = 60

    # Rate limiting
    requests_per_minute: int = 60
    tokens_per_minute: int = 90000

    # Retry configuration
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    retry_backoff_multiplier: float = 2.0

    # VP-AI: Provider fallback configuration
    enable_fallback: bool = True
    fallback_providers: list[LLMProvider] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Set default fallback providers if not specified."""
        if self.enable_fallback and not self.fallback_providers:
            # Default: fallback to the other provider
            if self.provider == LLMProvider.OPENAI:
                self.fallback_providers = [LLMProvider.ANTHROPIC]
            else:
                self.fallback_providers = [LLMProvider.OPENAI]


@dataclass
class TokenUsage:
    """Token usage tracking."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class CostEstimate:
    """Cost estimation for API calls."""

    prompt_cost: float = 0.0
    completion_cost: float = 0.0
    total_cost: float = 0.0
    currency: str = "USD"


@dataclass
class LLMResponse:
    """Response from LLM API call."""

    content: str
    model: str
    provider: LLMProvider
    token_usage: TokenUsage
    cost_estimate: CostEstimate
    latency_ms: float
    finish_reason: str = "stop"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMMessage:
    """A message in a conversation."""

    role: str  # "system", "user", "assistant"
    content: str


# ============================================================================
# Token Counting and Cost Estimation
# ============================================================================


# Pricing per 1K tokens (as of late 2024, approximate)
PRICING: dict[str, dict[str, float]] = {
    # OpenAI pricing
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    # Anthropic pricing (per 1K tokens)
    "claude-opus-4-6": {"input": 0.015, "output": 0.075},
    "claude-sonnet-4-5-20250929": {"input": 0.003, "output": 0.015},
    "claude-haiku-4-5-20251001": {"input": 0.0008, "output": 0.004},
    "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
    "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
    "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
}


def estimate_tokens(text: str) -> int:
    """Estimate token count for text.

    Uses a simple heuristic: ~4 characters per token.
    For accurate counts, use tiktoken for OpenAI or the Anthropic tokenizer.

    Args:
        text: Input text to estimate tokens for.

    Returns:
        Estimated token count.
    """
    # Simple heuristic: approximately 4 characters per token
    return len(text) // 4


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> CostEstimate:
    """Estimate cost for an API call.

    Args:
        model: Model name.
        prompt_tokens: Number of input tokens.
        completion_tokens: Number of output tokens.

    Returns:
        CostEstimate with calculated costs.
    """
    pricing = PRICING.get(model, {"input": 0.001, "output": 0.002})

    prompt_cost = (prompt_tokens / 1000) * pricing["input"]
    completion_cost = (completion_tokens / 1000) * pricing["output"]

    return CostEstimate(
        prompt_cost=round(prompt_cost, 6),
        completion_cost=round(completion_cost, 6),
        total_cost=round(prompt_cost + completion_cost, 6),
        currency="USD",
    )


# ============================================================================
# Rate Limiter
# ============================================================================


class RateLimiter:
    """Token bucket rate limiter for API calls."""

    def __init__(self, requests_per_minute: int, tokens_per_minute: int):
        """Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests allowed per minute.
            tokens_per_minute: Maximum tokens allowed per minute.
        """
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute
        self._request_timestamps: list[float] = []
        self._token_usage: list[tuple[float, int]] = []
        self._lock = threading.Lock()

    def _clean_old_entries(self, current_time: float) -> None:
        """Remove entries older than 1 minute."""
        cutoff = current_time - 60.0

        self._request_timestamps = [
            ts for ts in self._request_timestamps if ts > cutoff
        ]
        self._token_usage = [
            (ts, tokens) for ts, tokens in self._token_usage if ts > cutoff
        ]

    def can_proceed(self, estimated_tokens: int) -> tuple[bool, float]:
        """Check if a request can proceed.

        Args:
            estimated_tokens: Estimated tokens for the request.

        Returns:
            Tuple of (can_proceed, wait_time_seconds).
        """
        current_time = time.time()

        with self._lock:
            self._clean_old_entries(current_time)

            # Check request limit
            if len(self._request_timestamps) >= self.requests_per_minute:
                wait_time = self._request_timestamps[0] + 60.0 - current_time
                return False, max(0, wait_time)

            # Check token limit
            current_tokens = sum(tokens for _, tokens in self._token_usage)
            if current_tokens + estimated_tokens > self.tokens_per_minute:
                if self._token_usage:
                    wait_time = self._token_usage[0][0] + 60.0 - current_time
                    return False, max(0, wait_time)

            return True, 0.0

    def record_usage(self, tokens: int) -> None:
        """Record a completed request.

        Args:
            tokens: Tokens used in the request.
        """
        current_time = time.time()

        with self._lock:
            self._request_timestamps.append(current_time)
            self._token_usage.append((current_time, tokens))

    async def wait_if_needed(self, estimated_tokens: int) -> None:
        """Wait if rate limit would be exceeded.

        Args:
            estimated_tokens: Estimated tokens for the request.
        """
        while True:
            can_proceed, wait_time = self.can_proceed(estimated_tokens)
            if can_proceed:
                return
            logger.debug(f"Rate limit reached, waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time + 0.1)


# ============================================================================
# Abstract LLM Client
# ============================================================================


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        model: str,
        max_tokens: int,
        temperature: float,
        timeout: int,
    ) -> LLMResponse:
        """Generate a response from the LLM.

        Args:
            messages: List of conversation messages.
            model: Model name to use.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            timeout: Request timeout in seconds.

        Returns:
            LLMResponse with generated content.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the client is properly configured and available.

        Returns:
            True if the client can be used.
        """
        pass


# ============================================================================
# OpenAI Client
# ============================================================================


class OpenAIClient(BaseLLMClient):
    """Client for OpenAI API (also used for xAI Grok via base_url)."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        """Initialize OpenAI client.

        Args:
            api_key: OpenAI API key. If None, uses config.
            base_url: Custom API base URL (e.g. for xAI Grok).
        """
        self._api_key = api_key or getattr(settings, "openai_api_key", None)
        self._base_url = base_url
        self._client = None

    def _get_client(self) -> Any:
        """Get or create the OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI

                kwargs: dict[str, Any] = {"api_key": self._api_key}
                if self._base_url:
                    kwargs["base_url"] = self._base_url
                self._client = AsyncOpenAI(**kwargs)
            except ImportError:
                raise ImportError(
                    "openai package not installed. Install with: pip install openai"
                )
        return self._client

    def is_available(self) -> bool:
        """Check if OpenAI client is available."""
        return bool(self._api_key)

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str,
        max_tokens: int,
        temperature: float,
        timeout: int,
    ) -> LLMResponse:
        """Generate response using OpenAI API."""
        start_time = time.perf_counter()

        client = self._get_client()

        # Convert messages to OpenAI format
        openai_messages = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]

        response = await client.chat.completions.create(
            model=model,
            messages=openai_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
        )

        latency_ms = (time.perf_counter() - start_time) * 1000

        # Extract usage
        usage = response.usage
        token_usage = TokenUsage(
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
        )

        # Calculate cost
        cost = estimate_cost(
            model, token_usage.prompt_tokens, token_usage.completion_tokens
        )

        content = response.choices[0].message.content or ""
        finish_reason = response.choices[0].finish_reason or "stop"

        return LLMResponse(
            content=content,
            model=model,
            provider=LLMProvider.OPENAI,
            token_usage=token_usage,
            cost_estimate=cost,
            latency_ms=round(latency_ms, 2),
            finish_reason=finish_reason,
            metadata={"response_id": response.id},
        )


# ============================================================================
# Anthropic Client
# ============================================================================


class AnthropicClient(BaseLLMClient):
    """Client for Anthropic Claude API."""

    def __init__(self, api_key: str | None = None):
        """Initialize Anthropic client.

        Args:
            api_key: Anthropic API key. If None, uses config.
        """
        self._api_key = api_key or getattr(settings, "anthropic_api_key", None)
        self._client = None

    def _get_client(self) -> Any:
        """Get or create the Anthropic client."""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic

                self._client = AsyncAnthropic(api_key=self._api_key)
            except ImportError:
                raise ImportError(
                    "anthropic package not installed. Install with: pip install anthropic"
                )
        return self._client

    def is_available(self) -> bool:
        """Check if Anthropic client is available."""
        return bool(self._api_key)

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str,
        max_tokens: int,
        temperature: float,
        timeout: int,
    ) -> LLMResponse:
        """Generate response using Anthropic API."""
        start_time = time.perf_counter()

        client = self._get_client()

        # Extract system message if present
        system_message = None
        anthropic_messages = []

        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                anthropic_messages.append({"role": msg.role, "content": msg.content})

        # Call Claude API
        kwargs = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "timeout": timeout,
        }
        if system_message:
            kwargs["system"] = system_message

        response = await client.messages.create(**kwargs)

        latency_ms = (time.perf_counter() - start_time) * 1000

        # Extract usage
        usage = response.usage
        token_usage = TokenUsage(
            prompt_tokens=usage.input_tokens if usage else 0,
            completion_tokens=usage.output_tokens if usage else 0,
            total_tokens=(usage.input_tokens + usage.output_tokens) if usage else 0,
        )

        # Calculate cost
        cost = estimate_cost(
            model, token_usage.prompt_tokens, token_usage.completion_tokens
        )

        # Extract content
        content = ""
        if response.content:
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text

        return LLMResponse(
            content=content,
            model=model,
            provider=LLMProvider.ANTHROPIC,
            token_usage=token_usage,
            cost_estimate=cost,
            latency_ms=round(latency_ms, 2),
            finish_reason=response.stop_reason or "end_turn",
            metadata={"response_id": response.id},
        )


# ============================================================================
# Google Gemini Client (BYOK only)
# ============================================================================


class _GoogleMarkerClient(BaseLLMClient):
    """Marker client for Google Gemini — uses google-genai SDK."""

    def __init__(self, api_key: str):
        self._api_key = api_key

    def is_available(self) -> bool:
        return bool(self._api_key)

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str,
        max_tokens: int,
        temperature: float,
        timeout: int,
    ) -> LLMResponse:
        """Generate response using Google Gemini API."""
        start_time = time.perf_counter()

        try:
            from google import genai
        except ImportError:
            raise ImportError(
                "google-genai package not installed. Install with: pip install google-genai"
            )

        client = genai.Client(api_key=self._api_key)

        # Build prompt from messages
        system_text = ""
        user_text = ""
        for msg in messages:
            if msg.role == "system":
                system_text = msg.content
            else:
                user_text += msg.content

        contents = f"{system_text}\n\n{user_text}" if system_text else user_text

        # google-genai is sync — run in thread
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model,
            contents=contents,
        )

        latency_ms = (time.perf_counter() - start_time) * 1000

        content = response.text or ""
        token_usage = TokenUsage()

        return LLMResponse(
            content=content,
            model=model,
            provider=LLMProvider.GOOGLE,
            token_usage=token_usage,
            cost_estimate=0.0,
            latency_ms=round(latency_ms, 2),
            finish_reason="stop",
            metadata={},
        )


# ============================================================================
# Ollama Client (Local Models)
# ============================================================================


class OllamaClient(BaseLLMClient):
    """Client for Ollama local model inference.

    Connects to a local Ollama instance (default http://localhost:11434)
    to run open-source models like medgemma, qwen3, nemotron, etc.
    No API key required — completely free.
    """

    def __init__(self, base_url: str = "http://localhost:11434"):
        self._base_url = base_url.rstrip("/")

    def is_available(self) -> bool:
        """Check if Ollama is running locally."""
        try:
            import httpx
            resp = httpx.get(f"{self._base_url}/api/tags", timeout=2.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str,
        max_tokens: int,
        temperature: float,
        timeout: int,
    ) -> LLMResponse:
        """Generate response using local Ollama instance."""
        import httpx

        start_time = time.perf_counter()

        ollama_messages = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": model,
                    "messages": ollama_messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()

        latency_ms = (time.perf_counter() - start_time) * 1000

        content = data.get("message", {}).get("content", "")

        # Ollama returns eval_count / prompt_eval_count
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)
        token_usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

        return LLMResponse(
            content=content,
            model=model,
            provider=LLMProvider.OLLAMA,
            token_usage=token_usage,
            cost_estimate=CostEstimate(),  # Free — local inference
            latency_ms=round(latency_ms, 2),
            finish_reason="stop",
            metadata={"ollama_total_duration": data.get("total_duration", 0)},
        )

    @staticmethod
    async def list_models(base_url: str = "http://localhost:11434") -> list[dict]:
        """List locally installed Ollama models."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{base_url.rstrip('/')}/api/tags")
                resp.raise_for_status()
                data = resp.json()
                return [
                    {
                        "id": m["name"],
                        "name": m["name"].split(":")[0].replace("/", " / "),
                        "tier": "local",
                        "size_gb": round(m.get("size", 0) / 1e9, 1),
                    }
                    for m in data.get("models", [])
                ]
        except Exception:
            return []


# ============================================================================
# Main LLM Service
# ============================================================================


class LLMService:
    """Unified service for LLM interactions.

    Provides:
    - Multiple provider support (OpenAI, Anthropic)
    - Rate limiting
    - Retry logic with exponential backoff
    - Token counting and cost estimation
    - Logging and metrics
    """

    def __init__(self, config: LLMConfig | None = None):
        """Initialize LLM service.

        Args:
            config: Service configuration. If None, uses defaults from settings.
        """
        self.config = config or self._load_config_from_settings()

        # Initialize clients
        self._openai_client = OpenAIClient()
        self._anthropic_client = AnthropicClient()

        # Initialize rate limiter
        self._rate_limiter = RateLimiter(
            self.config.requests_per_minute,
            self.config.tokens_per_minute,
        )

        # Metrics
        self._total_requests = 0
        self._total_tokens = 0
        self._total_cost = 0.0
        self._errors = 0

        logger.info(
            f"LLMService initialized with provider={self.config.provider.value}, "
            f"model={self.config.model}"
        )

    def _load_config_from_settings(self) -> LLMConfig:
        """Load configuration from application settings."""
        provider_str = getattr(settings, "llm_provider", "openai")
        try:
            provider = LLMProvider(provider_str.lower())
        except ValueError:
            provider = LLMProvider.OPENAI

        return LLMConfig(
            provider=provider,
            model=getattr(settings, "llm_model", "claude-opus-4-6"),
            max_tokens=getattr(settings, "llm_max_tokens", 4096),
        )

    def _get_byok_config(self) -> dict | None:
        """Check for BYOK (Bring Your Own Key) override."""
        try:
            from app.api.llm_settings import get_byok_config
            return get_byok_config()
        except ImportError:
            return None

    def _get_client(self, provider: LLMProvider | None = None) -> BaseLLMClient:
        """Get the appropriate client for the provider.

        Checks BYOK config first — if the user has configured a custom API key,
        creates an ad-hoc client with that key instead of the system default.

        Args:
            provider: Provider to use. If None, uses config default.

        Returns:
            The LLM client for the provider.

        Raises:
            ValueError: If the provider is not configured.
        """
        byok = self._get_byok_config()

        # Use BYOK provider if no explicit override
        if provider is None and byok and byok.get("provider"):
            try:
                provider = LLMProvider(byok["provider"])
            except ValueError:
                provider = self.config.provider
        else:
            provider = provider or self.config.provider

        # Check for BYOK API key for this provider
        byok_key = None
        if byok and byok.get("api_key") and byok.get("provider") == provider.value:
            byok_key = byok["api_key"]

        if provider == LLMProvider.OPENAI:
            if byok_key:
                return OpenAIClient(api_key=byok_key)
            if not self._openai_client.is_available():
                raise ValueError(
                    "OpenAI API key not configured. Set OPENAI_API_KEY environment variable."
                )
            return self._openai_client

        if provider == LLMProvider.ANTHROPIC:
            if byok_key:
                return AnthropicClient(api_key=byok_key)
            if not self._anthropic_client.is_available():
                raise ValueError(
                    "Anthropic API key not configured. Set ANTHROPIC_API_KEY environment variable."
                )
            return self._anthropic_client

        if provider == LLMProvider.XAI:
            # xAI uses OpenAI-compatible API with different base URL
            if byok_key:
                return OpenAIClient(api_key=byok_key, base_url="https://api.x.ai/v1")
            raise ValueError("xAI requires a BYOK API key. Configure one in Settings > AI / LLM.")

        if provider == LLMProvider.GOOGLE:
            # Google Gemini needs its own SDK — handled specially in generate()
            if not byok_key:
                raise ValueError("Google Gemini requires a BYOK API key. Configure one in Settings > AI / LLM.")
            # Return a marker; generate() handles Google directly
            return _GoogleMarkerClient(api_key=byok_key)

        if provider == LLMProvider.OLLAMA:
            base_url = "http://localhost:11434"
            if byok and byok.get("ollama_base_url"):
                base_url = byok["ollama_base_url"]
            return OllamaClient(base_url=base_url)

        raise ValueError(f"Unknown provider: {provider}")

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        provider: LLMProvider | None = None,
    ) -> LLMResponse:
        """Generate a response from the LLM.

        Args:
            prompt: User prompt/input.
            system_prompt: Optional system prompt for context.
            model: Model to use (overrides config).
            max_tokens: Max tokens to generate (overrides config).
            temperature: Sampling temperature (overrides config).
            provider: Provider to use (overrides config).

        Returns:
            LLMResponse with generated content.

        Raises:
            Exception: If generation fails after all retries.
        """
        # Check BYOK overrides for model/provider
        byok = self._get_byok_config()
        if byok and byok.get("provider") and provider is None:
            try:
                provider = LLMProvider(byok["provider"])
            except ValueError:
                provider = self.config.provider
        else:
            provider = provider or self.config.provider

        if byok and byok.get("model") and model is None:
            model = byok["model"]
        else:
            model = model or self.config.model

        max_tokens = max_tokens or self.config.max_tokens
        temperature = temperature if temperature is not None else self.config.temperature

        # Build messages
        messages = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        messages.append(LLMMessage(role="user", content=prompt))

        # Estimate tokens for rate limiting
        total_text = (system_prompt or "") + prompt
        estimated_tokens = estimate_tokens(total_text) + max_tokens

        # Wait for rate limit
        await self._rate_limiter.wait_if_needed(estimated_tokens)

        # Get client
        client = self._get_client(provider)

        # Retry loop
        last_error = None
        delay = self.config.retry_delay_seconds

        for attempt in range(self.config.max_retries):
            try:
                response = await client.generate(
                    messages=messages,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=self.config.timeout_seconds,
                )

                # Record usage
                self._rate_limiter.record_usage(response.token_usage.total_tokens)
                self._total_requests += 1
                self._total_tokens += response.token_usage.total_tokens
                self._total_cost += response.cost_estimate.total_cost

                logger.debug(
                    f"LLM response: {response.token_usage.total_tokens} tokens, "
                    f"${response.cost_estimate.total_cost:.4f}, "
                    f"{response.latency_ms:.0f}ms"
                )

                return response

            except (ImportError, ValueError) as e:
                # Non-transient errors - fail immediately without retrying
                self._errors += 1
                raise Exception(f"LLM configuration error: {e}")

            except Exception as e:
                last_error = e
                self._errors += 1
                logger.warning(
                    f"LLM request failed (attempt {attempt + 1}/{self.config.max_retries}): {e}"
                )

                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(delay)
                    delay *= self.config.retry_backoff_multiplier

        # VP-AI: Try fallback providers if configured
        if self.config.enable_fallback and self.config.fallback_providers:
            for fallback_provider in self.config.fallback_providers:
                if fallback_provider == provider:
                    continue  # Skip if same as primary
                try:
                    fallback_client = self._get_client(fallback_provider)
                    if not fallback_client.is_available():
                        continue

                    # Get appropriate model for fallback provider
                    fallback_model = self._get_fallback_model(fallback_provider)

                    logger.info(
                        f"Primary LLM failed, trying fallback provider: {fallback_provider.value}"
                    )

                    response = await fallback_client.generate(
                        messages=messages,
                        model=fallback_model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        timeout=self.config.timeout_seconds,
                    )

                    # Record usage
                    self._rate_limiter.record_usage(response.token_usage.total_tokens)
                    self._total_requests += 1
                    self._total_tokens += response.token_usage.total_tokens
                    self._total_cost += response.cost_estimate.total_cost

                    logger.info(
                        f"Fallback to {fallback_provider.value} succeeded"
                    )

                    return response

                except Exception as fallback_error:
                    logger.warning(
                        f"Fallback provider {fallback_provider.value} also failed: {fallback_error}"
                    )
                    continue

        raise Exception(f"LLM request failed after {self.config.max_retries} retries: {last_error}")

    def _get_fallback_model(self, provider: LLMProvider) -> str:
        """Get the default model for a fallback provider.

        VP-AI: Maps to equivalent models when falling back to different providers.

        Args:
            provider: The fallback provider.

        Returns:
            Default model name for the provider.
        """
        if provider == LLMProvider.OPENAI:
            return "gpt-5.2-chat-latest"  # Cost-effective default
        elif provider == LLMProvider.ANTHROPIC:
            return "claude-opus-4-6"  # Most capable default
        elif provider == LLMProvider.GOOGLE:
            return "gemini-3-flash-preview"
        elif provider == LLMProvider.XAI:
            return "grok-3-mini"
        elif provider == LLMProvider.OLLAMA:
            return "qwen3:latest"  # Fast default for local
        return "claude-opus-4-6"

    async def generate_chat(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        provider: LLMProvider | None = None,
    ) -> LLMResponse:
        """Generate a response from a multi-turn conversation.

        Args:
            messages: List of conversation messages.
            model: Model to use (overrides config).
            max_tokens: Max tokens to generate (overrides config).
            temperature: Sampling temperature (overrides config).
            provider: Provider to use (overrides config).

        Returns:
            LLMResponse with generated content.
        """
        # Check BYOK overrides for model/provider
        byok = self._get_byok_config()
        if byok and byok.get("provider") and provider is None:
            try:
                provider = LLMProvider(byok["provider"])
            except ValueError:
                provider = self.config.provider
        else:
            provider = provider or self.config.provider

        if byok and byok.get("model") and model is None:
            model = byok["model"]
        else:
            model = model or self.config.model

        max_tokens = max_tokens or self.config.max_tokens
        temperature = temperature if temperature is not None else self.config.temperature

        # Estimate tokens
        total_text = " ".join(msg.content for msg in messages)
        estimated_tokens = estimate_tokens(total_text) + max_tokens

        # Wait for rate limit
        await self._rate_limiter.wait_if_needed(estimated_tokens)

        # Get client
        client = self._get_client(provider)

        # Retry loop
        last_error = None
        delay = self.config.retry_delay_seconds

        for attempt in range(self.config.max_retries):
            try:
                response = await client.generate(
                    messages=messages,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=self.config.timeout_seconds,
                )

                # Record usage
                self._rate_limiter.record_usage(response.token_usage.total_tokens)
                self._total_requests += 1
                self._total_tokens += response.token_usage.total_tokens
                self._total_cost += response.cost_estimate.total_cost

                return response

            except (ImportError, ValueError) as e:
                # Non-transient errors - fail immediately without retrying
                self._errors += 1
                raise Exception(f"LLM configuration error: {e}")

            except Exception as e:
                last_error = e
                self._errors += 1
                logger.warning(
                    f"LLM chat request failed (attempt {attempt + 1}/{self.config.max_retries}): {e}"
                )

                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(delay)
                    delay *= self.config.retry_backoff_multiplier

        # VP-AI: Try fallback providers if configured
        if self.config.enable_fallback and self.config.fallback_providers:
            for fallback_provider in self.config.fallback_providers:
                if fallback_provider == provider:
                    continue
                try:
                    fallback_client = self._get_client(fallback_provider)
                    if not fallback_client.is_available():
                        continue

                    fallback_model = self._get_fallback_model(fallback_provider)

                    logger.info(
                        f"Primary LLM chat failed, trying fallback: {fallback_provider.value}"
                    )

                    response = await fallback_client.generate(
                        messages=messages,
                        model=fallback_model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        timeout=self.config.timeout_seconds,
                    )

                    self._rate_limiter.record_usage(response.token_usage.total_tokens)
                    self._total_requests += 1
                    self._total_tokens += response.token_usage.total_tokens
                    self._total_cost += response.cost_estimate.total_cost

                    return response

                except Exception as fallback_error:
                    logger.warning(
                        f"Fallback {fallback_provider.value} also failed: {fallback_error}"
                    )
                    continue

        raise Exception(
            f"LLM chat request failed after {self.config.max_retries} retries: {last_error}"
        )

    def get_available_providers(self) -> list[LLMProvider]:
        """Get list of configured providers.

        Returns:
            List of available LLM providers.
        """
        available = []
        if self._openai_client.is_available():
            available.append(LLMProvider.OPENAI)
        if self._anthropic_client.is_available():
            available.append(LLMProvider.ANTHROPIC)
        if OllamaClient().is_available():
            available.append(LLMProvider.OLLAMA)
        return available

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics.

        Returns:
            Dictionary with usage statistics.
        """
        return {
            "provider": self.config.provider.value,
            "model": self.config.model,
            "total_requests": self._total_requests,
            "total_tokens": self._total_tokens,
            "total_cost_usd": round(self._total_cost, 4),
            "errors": self._errors,
            "available_providers": [p.value for p in self.get_available_providers()],
        }


# ============================================================================
# Singleton Pattern
# ============================================================================


_service_instance: LLMService | None = None
_service_lock = threading.Lock()


def get_llm_service(config: LLMConfig | None = None) -> LLMService:
    """Get or create the singleton LLM service instance.

    Args:
        config: Optional configuration for the service.

    Returns:
        LLMService singleton instance.
    """
    global _service_instance

    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = LLMService(config)

    return _service_instance


def reset_llm_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _service_instance
    with _service_lock:
        _service_instance = None
