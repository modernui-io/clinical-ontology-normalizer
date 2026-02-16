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


PROVIDER_MODELS = {
    "anthropic": [
        {"id": "claude-opus-4-6", "name": "Claude Opus 4.6", "tier": "flagship"},
        {"id": "claude-sonnet-4-5-20250929", "name": "Claude Sonnet 4.5", "tier": "balanced"},
        {"id": "claude-haiku-4-5-20251001", "name": "Claude Haiku 4.5", "tier": "fast"},
        {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "tier": "balanced"},
        {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus", "tier": "flagship"},
        {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku", "tier": "fast"},
    ],
    "openai": [
        {"id": "gpt-4o", "name": "GPT-4o", "tier": "flagship"},
        {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "tier": "fast"},
        {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "tier": "balanced"},
        {"id": "gpt-4", "name": "GPT-4", "tier": "flagship"},
        {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "tier": "fast"},
    ],
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
    # Always show both as options — user can bring their own key
    for p in ["anthropic", "openai"]:
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

    # Validate model belongs to provider
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
    """Return the list of supported models for each provider."""
    return ModelsResponse(providers=PROVIDER_MODELS)
