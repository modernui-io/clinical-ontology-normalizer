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


class LLMModel(str, Enum):
    """Supported LLM models."""

    # OpenAI models
    GPT4O = "gpt-4o"
    GPT4O_MINI = "gpt-4o-mini"
    GPT4_TURBO = "gpt-4-turbo"
    GPT4 = "gpt-4"
    GPT35_TURBO = "gpt-3.5-turbo"

    # Anthropic models
    CLAUDE_OPUS_4_6 = "claude-opus-4-6"
    CLAUDE_SONNET_4_5 = "claude-sonnet-4-5-20250929"
    CLAUDE_HAIKU_4_5 = "claude-haiku-4-5-20251001"
    CLAUDE_3_5_SONNET = "claude-3-5-sonnet-20241022"
    CLAUDE_3_OPUS = "claude-3-opus-20240229"
    CLAUDE_3_SONNET = "claude-3-sonnet-20240229"
    CLAUDE_3_HAIKU = "claude-3-haiku-20240307"


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
    """Client for OpenAI API."""

    def __init__(self, api_key: str | None = None):
        """Initialize OpenAI client.

        Args:
            api_key: OpenAI API key. If None, uses config.
        """
        self._api_key = api_key or getattr(settings, "openai_api_key", None)
        self._client = None

    def _get_client(self) -> Any:
        """Get or create the OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(api_key=self._api_key)
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

    def _get_client(self, provider: LLMProvider | None = None) -> BaseLLMClient:
        """Get the appropriate client for the provider.

        Args:
            provider: Provider to use. If None, uses config default.

        Returns:
            The LLM client for the provider.

        Raises:
            ValueError: If the provider is not configured.
        """
        provider = provider or self.config.provider

        if provider == LLMProvider.OPENAI:
            if not self._openai_client.is_available():
                raise ValueError(
                    "OpenAI API key not configured. Set OPENAI_API_KEY environment variable."
                )
            return self._openai_client

        if provider == LLMProvider.ANTHROPIC:
            if not self._anthropic_client.is_available():
                raise ValueError(
                    "Anthropic API key not configured. Set ANTHROPIC_API_KEY environment variable."
                )
            return self._anthropic_client

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
        model = model or self.config.model
        max_tokens = max_tokens or self.config.max_tokens
        temperature = temperature if temperature is not None else self.config.temperature
        provider = provider or self.config.provider

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
            return "gpt-4o-mini"  # Cost-effective default
        elif provider == LLMProvider.ANTHROPIC:
            return "claude-opus-4-6"  # Most capable default
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
        model = model or self.config.model
        max_tokens = max_tokens or self.config.max_tokens
        temperature = temperature if temperature is not None else self.config.temperature
        provider = provider or self.config.provider

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
