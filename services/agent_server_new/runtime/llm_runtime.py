from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: str = "false") -> bool:
    return str(os.getenv(name, default) or default).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class LLMRuntimeConfig:
    enabled: bool
    provider: str
    model_id: str
    base_url: str
    api_key: str
    api_key_env_name: str
    ready: bool


def load_llm_runtime_from_env(*, runtime_profile: str) -> LLMRuntimeConfig:
    enabled = _env_bool("AGENT_LLM_ENABLED", "false")
    provider = str(os.getenv("AGENT_LLM_PROVIDER", "openai_compatible") or "openai_compatible").strip().lower()
    model_id = str(os.getenv("AGENT_LLM_MODEL_ID", "") or "").strip()
    base_url = str(os.getenv("AGENT_LLM_BASE_URL", "") or "").strip()
    api_key = str(os.getenv("AGENT_LLM_API_KEY", "") or "").strip()
    api_key_env_name = str(os.getenv("AGENT_LLM_API_KEY_ENV", "") or "").strip()
    if not api_key and api_key_env_name:
        api_key = str(os.getenv(api_key_env_name, "") or "").strip()

    ready = bool(model_id) and bool(api_key)
    if enabled and str(runtime_profile).strip().lower() in {"prod", "production"} and not ready:
        raise RuntimeError(
            "AGENT_LLM_ENABLED=true in production requires AGENT_LLM_MODEL_ID "
            "and AGENT_LLM_API_KEY (or AGENT_LLM_API_KEY_ENV)"
        )

    return LLMRuntimeConfig(
        enabled=enabled,
        provider=provider,
        model_id=model_id,
        base_url=base_url,
        api_key=api_key,
        api_key_env_name=api_key_env_name,
        ready=ready,
    )
