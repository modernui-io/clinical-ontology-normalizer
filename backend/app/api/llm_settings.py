"""LLM Settings API — Bring Your Own Key (BYOK) Configuration.

Allows users to configure their own LLM provider and API key
instead of using the system default. Supports:
- GET /llm-settings — current config (provider, model, key status)
- PUT /llm-settings — update config (provider, model, optional API key)
- POST /llm-settings/test — test connection with current or provided key
- GET /llm-settings/models — available models per provider
"""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm-settings", tags=["LLM Settings (BYOK)"])


# ============================================================================
# In-memory BYOK store (per-server, reset on restart)
# Production would use encrypted DB column per tenant.
# ============================================================================

_byok_lock = threading.Lock()
_byok_config: dict | None = None  # Single-tenant for v1


def _get_active_provider() -> str:
    """Return the active LLM provider — BYOK override or system default."""
    if _byok_config and _byok_config.get("provider"):
        return _byok_config["provider"]
    return settings.llm_provider


def _get_active_model() -> str:
    """Return the active LLM model — BYOK override or system default."""
    if _byok_config and _byok_config.get("model"):
        return _byok_config["model"]
    return settings.llm_model


def _get_active_api_key(provider: str) -> str | None:
    """Return the API key for a provider — BYOK override or system default."""
    if _byok_config and _byok_config.get("api_key") and _byok_config.get("provider") == provider:
        return _byok_config["api_key"]
    if provider == "anthropic":
        return settings.anthropic_api_key
    if provider == "openai":
        return settings.openai_api_key
    return None


# ============================================================================
# Public accessor for other services to use BYOK config
# ============================================================================

def get_byok_config() -> dict | None:
    """Get the current BYOK override config, if any.

    Returns dict with keys: provider, model, api_key (or None).
    Other services (narrative_extractor, llm_service, nlp_claude_api)
    can call this to check for user-supplied keys.
    """
    return _byok_config


# ============================================================================
# Models
# ============================================================================

class LLMProviderEnum(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    XAI = "xai"
    OLLAMA = "ollama"


PROVIDER_MODELS = {
    "anthropic": [
        {"id": "claude-opus-4-6", "name": "Claude Opus 4.6", "tier": "flagship"},
        {"id": "claude-sonnet-4-5-20250929", "name": "Claude Sonnet 4.5", "tier": "balanced"},
        {"id": "claude-haiku-4-5-20251001", "name": "Claude Haiku 4.5", "tier": "fast"},
    ],
    "openai": [
        {"id": "gpt-5.2", "name": "GPT-5.2 Thinking", "tier": "flagship"},
        {"id": "gpt-5.2-pro", "name": "GPT-5.2 Pro", "tier": "flagship"},
        {"id": "gpt-5.2-chat-latest", "name": "GPT-5.2 Instant", "tier": "balanced"},
        {"id": "gpt-5-codex", "name": "GPT-5 Codex", "tier": "flagship"},
        {"id": "gpt-4o", "name": "GPT-4o", "tier": "balanced"},
        {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "tier": "fast"},
    ],
    "google": [
        {"id": "gemini-3-pro-preview", "name": "Gemini 3 Pro", "tier": "flagship"},
        {"id": "gemini-3-flash-preview", "name": "Gemini 3 Flash", "tier": "balanced"},
        {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "tier": "flagship"},
        {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "tier": "balanced"},
        {"id": "gemini-2.5-flash-lite", "name": "Gemini 2.5 Flash Lite", "tier": "fast"},
    ],
    "xai": [
        {"id": "grok-4-1-fast-reasoning", "name": "Grok 4.1 Fast (Reasoning)", "tier": "flagship"},
        {"id": "grok-4-1-fast-non-reasoning", "name": "Grok 4.1 Fast", "tier": "balanced"},
        {"id": "grok-4-0709", "name": "Grok 4", "tier": "flagship"},
        {"id": "grok-code-fast-1", "name": "Grok Code Fast", "tier": "fast"},
        {"id": "grok-3", "name": "Grok 3", "tier": "balanced"},
        {"id": "grok-3-mini", "name": "Grok 3 Mini", "tier": "fast"},
    ],
    # Ollama models are auto-detected from the local instance.
    # This static list is a fallback; the /models endpoint populates dynamically.
    "ollama": [],
}


class LLMSettingsResponse(BaseModel):
    provider: str = Field(..., description="Active LLM provider")
    model: str = Field(..., description="Active model ID")
    is_byok: bool = Field(..., description="Whether a custom API key is active")
    has_system_key: bool = Field(..., description="Whether the system has a default key configured")
    key_hint: str | None = Field(None, description="Last 4 chars of the active key, e.g. '...xK9f'")
    available_providers: list[str] = Field(default_factory=list)


class LLMSettingsUpdateRequest(BaseModel):
    provider: LLMProviderEnum = Field(..., description="LLM provider to use")
    model: str = Field(..., description="Model ID (e.g. 'claude-opus-4-6')")
    api_key: str | None = Field(None, description="API key (omit to use system default)")


class LLMTestRequest(BaseModel):
    provider: LLMProviderEnum = Field(..., description="Provider to test")
    model: str = Field(..., description="Model to test")
    api_key: str | None = Field(None, description="Key to test (omit to test current active key)")


class LLMTestResponse(BaseModel):
    success: bool
    provider: str
    model: str
    latency_ms: float | None = None
    error: str | None = None


class ModelsResponse(BaseModel):
    providers: dict[str, list[dict]] = Field(..., description="Models per provider")


# ============================================================================
# Endpoints
# ============================================================================

@router.get(
    "",
    response_model=LLMSettingsResponse,
    summary="Get current LLM configuration",
)
async def get_llm_settings() -> LLMSettingsResponse:
    """Return the active LLM configuration, including BYOK status."""
    provider = _get_active_provider()
    model = _get_active_model()
    is_byok = _byok_config is not None and bool(_byok_config.get("api_key"))

    active_key = _get_active_api_key(provider)
    key_hint = f"...{active_key[-4:]}" if active_key and len(active_key) >= 4 else None

    has_system_key = bool(settings.anthropic_api_key or settings.openai_api_key)

    available = []
    if settings.anthropic_api_key or (is_byok and provider == "anthropic"):
        available.append("anthropic")
    if settings.openai_api_key or (is_byok and provider == "openai"):
        available.append("openai")
    # Always show all providers as options — user can bring their own key
    for p in ["anthropic", "openai", "google", "xai", "ollama"]:
        if p not in available:
            available.append(p)

    return LLMSettingsResponse(
        provider=provider,
        model=model,
        is_byok=is_byok,
        has_system_key=has_system_key,
        key_hint=key_hint,
        available_providers=available,
    )


@router.put(
    "",
    response_model=LLMSettingsResponse,
    summary="Update LLM configuration (BYOK)",
)
async def update_llm_settings(request: LLMSettingsUpdateRequest) -> LLMSettingsResponse:
    """Update the active LLM configuration.

    If api_key is provided, it becomes the BYOK key for this provider.
    If api_key is omitted/null, the system default key is used.
    """
    global _byok_config

    # Validate model belongs to provider (skip for Ollama — models are local/dynamic)
    if request.provider != LLMProviderEnum.OLLAMA:
        valid_models = [m["id"] for m in PROVIDER_MODELS.get(request.provider.value, [])]
        if request.model not in valid_models:
            raise HTTPException(
                status_code=400,
                detail=f"Model '{request.model}' is not valid for provider '{request.provider.value}'. "
                       f"Valid models: {valid_models}",
            )

    with _byok_lock:
        if request.api_key:
            _byok_config = {
                "provider": request.provider.value,
                "model": request.model,
                "api_key": request.api_key,
                "updated_at": time.time(),
            }
            logger.info(f"BYOK config updated: provider={request.provider.value}, model={request.model}")
        else:
            # Clear BYOK, revert to system defaults for this provider
            _byok_config = {
                "provider": request.provider.value,
                "model": request.model,
                "api_key": None,
                "updated_at": time.time(),
            }
            logger.info(f"LLM config updated (system key): provider={request.provider.value}, model={request.model}")

    return await get_llm_settings()


@router.post(
    "/test",
    response_model=LLMTestResponse,
    summary="Test LLM connection",
)
async def test_llm_connection(request: LLMTestRequest) -> LLMTestResponse:
    """Test that the LLM provider is reachable with the given or active key.

    Sends a minimal prompt to verify connectivity and key validity.
    """
    # Ollama doesn't need an API key — test connectivity directly
    if request.provider == LLMProviderEnum.OLLAMA:
        start = time.perf_counter()
        try:
            from app.services.llm_service import OllamaClient
            client = OllamaClient()
            if not client.is_available():
                return LLMTestResponse(
                    success=False,
                    provider="ollama",
                    model=request.model,
                    error="Ollama is not running. Start it with: ollama serve",
                )
            from app.services.llm_service import LLMMessage
            resp = await client.generate(
                messages=[LLMMessage(role="user", content="Say OK")],
                model=request.model,
                max_tokens=10,
                temperature=0.0,
                timeout=30,
            )
            latency_ms = (time.perf_counter() - start) * 1000
            return LLMTestResponse(
                success=True,
                provider="ollama",
                model=request.model,
                latency_ms=round(latency_ms, 1),
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            return LLMTestResponse(
                success=False,
                provider="ollama",
                model=request.model,
                latency_ms=round(latency_ms, 1),
                error=str(e),
            )

    api_key = request.api_key or _get_active_api_key(request.provider.value)

    if not api_key:
        return LLMTestResponse(
            success=False,
            provider=request.provider.value,
            model=request.model,
            error="No API key configured. Provide a key or set the system default.",
        )

    start = time.perf_counter()

    try:
        if request.provider == LLMProviderEnum.ANTHROPIC:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=request.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Say OK"}],
            )
            latency_ms = (time.perf_counter() - start) * 1000
            return LLMTestResponse(
                success=True,
                provider=request.provider.value,
                model=request.model,
                latency_ms=round(latency_ms, 1),
            )

        elif request.provider == LLMProviderEnum.OPENAI:
            import openai

            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=request.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Say OK"}],
            )
            latency_ms = (time.perf_counter() - start) * 1000
            return LLMTestResponse(
                success=True,
                provider=request.provider.value,
                model=request.model,
                latency_ms=round(latency_ms, 1),
            )

        elif request.provider == LLMProviderEnum.GOOGLE:
            from google import genai

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=request.model,
                contents="Say OK",
            )
            latency_ms = (time.perf_counter() - start) * 1000
            return LLMTestResponse(
                success=True,
                provider=request.provider.value,
                model=request.model,
                latency_ms=round(latency_ms, 1),
            )

        elif request.provider == LLMProviderEnum.XAI:
            # xAI Grok uses OpenAI-compatible API
            import openai

            client = openai.OpenAI(
                api_key=api_key,
                base_url="https://api.x.ai/v1",
            )
            response = client.chat.completions.create(
                model=request.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Say OK"}],
            )
            latency_ms = (time.perf_counter() - start) * 1000
            return LLMTestResponse(
                success=True,
                provider=request.provider.value,
                model=request.model,
                latency_ms=round(latency_ms, 1),
            )

    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        error_msg = str(e)
        # Sanitize: don't leak full key in error messages
        if api_key and api_key in error_msg:
            error_msg = error_msg.replace(api_key, "***")
        logger.warning(f"LLM connection test failed: {error_msg}")
        return LLMTestResponse(
            success=False,
            provider=request.provider.value,
            model=request.model,
            latency_ms=round(latency_ms, 1),
            error=error_msg,
        )


@router.delete(
    "",
    summary="Clear BYOK configuration",
)
async def clear_byok_config() -> dict:
    """Clear any BYOK override and revert to system defaults."""
    global _byok_config

    with _byok_lock:
        _byok_config = None

    logger.info("BYOK config cleared, reverted to system defaults")
    return {"status": "cleared", "message": "Reverted to system default LLM configuration"}


@router.get(
    "/models",
    response_model=ModelsResponse,
    summary="Get available models per provider",
)
async def get_available_models() -> ModelsResponse:
    """Return the list of supported models for each provider.

    Ollama models are auto-detected from the local instance.
    """
    providers = dict(PROVIDER_MODELS)

    # Auto-detect locally installed Ollama models
    try:
        from app.services.llm_service import OllamaClient
        ollama_models = await OllamaClient.list_models()
        if ollama_models:
            providers["ollama"] = ollama_models
        else:
            providers["ollama"] = [
                {"id": "(none installed)", "name": "No models found — run: ollama pull qwen3", "tier": "local"},
            ]
    except Exception:
        providers["ollama"] = [
            {"id": "(unavailable)", "name": "Ollama not running — start with: ollama serve", "tier": "local"},
        ]

    return ModelsResponse(providers=providers)
