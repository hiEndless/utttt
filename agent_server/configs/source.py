from __future__ import annotations

import logging
import os
import json
import time
from typing import Any, Dict, Optional

from agent_server.utils.db_utils import PostgresDB


logger = logging.getLogger(__name__)

ENV_USER_ID = "UTAKER_USER_ID"
ENV_DEFAULT_LLM_BASE_URL = "UTAKER_DEFAULT_LLM_BASE_URL"
ENV_DEFAULT_LLM_API_KEY = "UTAKER_DEFAULT_LLM_API_KEY"

_CACHE_CHECK_INTERVAL_SEC = 2.0
_cache_checked_at: dict[str | None, float] = {}
_cache_version_ts: dict[str | None, float] = {}
_cache_configs: dict[str | None, dict[str, dict[str, Any]]] = {}
_prefs_cache_checked_at: dict[str | None, float] = {}
_prefs_cache_version_ts: dict[str | None, float] = {}
_prefs_cache: dict[str | None, dict[str, Any]] = {}
_db_available_until: float = 0.0


DEFAULT_AGENT_CONFIGS: dict[str, dict[str, Any]] = {
    "news": {"model_id": "deepseek-ai/DeepSeek-V3", "language": "zh"},
    "kline": {"model_id": "Qwen/Qwen3-VL-235B-A22B-Instruct", "language": "zh"},
    "market_structure": {"model_id": "Qwen/Qwen3-VL-235B-A22B-Instruct", "language": "zh"},
    "human_market_narrator": {"model_id": "Qwen/Qwen3-VL-235B-A22B-Instruct", "language": "zh"},
    "signal_validation": {"model_id": "Qwen/Qwen3-VL-235B-A22B-Instruct", "language": "zh"},
    "position_risk": {"model_id": "Qwen/Qwen3-VL-235B-A22B-Instruct", "language": "zh"},
    "event_summary": {"model_id": "Qwen/Qwen3-VL-235B-A22B-Instruct", "language": "zh"},
    "trade_summary": {"model_id": "Qwen/Qwen3-VL-235B-A22B-Instruct", "language": "zh"},
    "trade_behavior": {"model_id": "qwen3-max", "language": "zh"},
    "decision": {"model_id": "Qwen/Qwen3-VL-235B-A22B-Instruct", "language": "zh"},
}

REQUIRED_AGENT_NAMES: tuple[str, ...] = (
    "kline",
    "human_market_narrator",
    "signal_validation",
    "decision",
    "position_risk",
    "market_structure",
    "trade_behavior",
)


def _resolve_user_id(user_id: Optional[str]) -> Optional[str]:
    if user_id:
        return user_id
    v = os.getenv(ENV_USER_ID)
    return v.strip() if v and v.strip() else None


def _default_llm_base_url() -> Optional[str]:
    v = os.getenv(ENV_DEFAULT_LLM_BASE_URL)
    return v.strip() if v and v.strip() else None


def _default_llm_api_key() -> Optional[str]:
    v = os.getenv(ENV_DEFAULT_LLM_API_KEY)
    if v and v.strip():
        return v.strip()
    v2 = os.getenv("SILICONFLOW_TOKEN")
    return v2.strip() if v2 and v2.strip() else None


def _db_enabled() -> bool:
    required = ["DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_DATABASE"]
    return all(os.getenv(k) and str(os.getenv(k)).strip() for k in required)


def _should_skip_db() -> bool:
    global _db_available_until
    if not _db_enabled():
        return True
    now = time.time()
    return now < _db_available_until


def _mark_db_temporarily_unavailable(seconds: float = 30.0) -> None:
    global _db_available_until
    _db_available_until = max(_db_available_until, time.time() + float(seconds))


def _normalize_lang(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, dict):
        for k in ("locale", "language", "lang", "value"):
            if k in value:
                return _normalize_lang(value.get(k))
        return None
    s = str(value).strip()
    if not s:
        return None
    low = s.lower()
    supported = {
        "zh": "zh",
        "en": "en",
        "zh-tw": "zh-TW",
        "ja": "ja",
        "ko": "ko",
        "es": "es",
        "pt": "pt",
        "ar": "ar",
        "de": "de",
        "ru": "ru",
        "fr": "fr",
        "it": "it",
    }
    if low in supported:
        return supported[low]

    if low.startswith("zh-") or low.startswith("zh_"):
        if "tw" in low or "hk" in low or "hant" in low:
            return "zh-TW"
        return "zh"
    if low.startswith("en-") or low.startswith("en_"):
        return "en"
    if low.startswith("pt-") or low.startswith("pt_"):
        return "pt"

    return s


def _normalize_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, dict):
        for k in ("enabled", "value", "on", "flag"):
            if k in value:
                return _normalize_bool(value.get(k))
        return None
    s = str(value).strip()
    if not s:
        return None
    low = s.lower()
    if low in ("true", "1", "yes", "y", "on"):
        return True
    if low in ("false", "0", "no", "n", "off"):
        return False
    try:
        obj = json.loads(s)
        return _normalize_bool(obj)
    except Exception:
        return None


def _get_config_version_ts(user_id: Optional[str]) -> float:
    uid = _resolve_user_id(user_id)
    if _should_skip_db():
        return 0.0
    sql = """
    SELECT EXTRACT(EPOCH FROM GREATEST(
      COALESCE(MAX(c.updated_at), TO_TIMESTAMP(0)),
      COALESCE(MAX(p.updated_at), TO_TIMESTAMP(0))
    )) AS version_ts
    FROM agent_model_configs c
    LEFT JOIN model_providers p ON p.id = c.provider_id
    WHERE c.deleted_at IS NULL
      AND c.is_active = TRUE
      AND (
        (%(uid)s IS NULL AND c.user_id IS NULL)
        OR (%(uid)s IS NOT NULL AND (c.user_id = (%(uid)s)::uuid OR c.user_id IS NULL))
      )
      AND (
        p.id IS NULL OR (
          p.deleted_at IS NULL
          AND p.is_active = TRUE
          AND (
            (%(uid)s IS NULL AND p.user_id IS NULL)
            OR (%(uid)s IS NOT NULL AND (p.user_id = (%(uid)s)::uuid OR p.user_id IS NULL))
          )
        )
      )
    """
    try:
        db = PostgresDB()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"uid": uid})
                row = cur.fetchone()
                if not row:
                    return 0.0
                try:
                    return float(row[0] or 0.0)
                except Exception:
                    return 0.0
    except Exception as e:
        _mark_db_temporarily_unavailable()
        logger.warning(f"读取 Agent 模型配置版本失败，将使用回退配置：{e}")
        return 0.0


def _load_configs_from_db(user_id: Optional[str]) -> dict[str, dict[str, Any]]:
    uid = _resolve_user_id(user_id)
    if _should_skip_db():
        return {}
    sql = """
    SELECT DISTINCT ON (c.agent_name)
      c.agent_name AS agent_name,
      c.model_id AS model_id,
      p.base_url AS llm_base_url,
      p.api_key AS llm_api_key,
      p.provider AS provider
    FROM agent_model_configs c
    JOIN model_providers p ON p.id = c.provider_id
    WHERE c.deleted_at IS NULL
      AND c.is_active = TRUE
      AND p.deleted_at IS NULL
      AND p.is_active = TRUE
      AND (
        (%(uid)s IS NULL AND c.user_id IS NULL)
        OR (%(uid)s IS NOT NULL AND (c.user_id = (%(uid)s)::uuid OR c.user_id IS NULL))
      )
      AND (
        (%(uid)s IS NULL AND p.user_id IS NULL)
        OR (%(uid)s IS NOT NULL AND (p.user_id = (%(uid)s)::uuid OR p.user_id IS NULL))
      )
    ORDER BY
      c.agent_name,
      (c.user_id IS NULL) ASC,
      c.updated_at DESC,
      (p.user_id IS NULL) ASC,
      p.updated_at DESC
    """
    out: dict[str, dict[str, Any]] = {}
    try:
        db = PostgresDB()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"uid": uid})
                rows = cur.fetchall() or []
                for r in rows:
                    agent_name = str(r[0] or "").strip()
                    if not agent_name:
                        continue
                    out[agent_name] = {
                        "model_id": r[1],
                        "llm_base_url": r[2],
                        "llm_api_key": r[3],
                        "provider": r[4],
                    }
    except Exception as e:
        _mark_db_temporarily_unavailable()
        raise e
    return out


def _get_prefs_version_ts(user_id: Optional[str]) -> float:
    uid = _resolve_user_id(user_id)
    if _should_skip_db():
        return 0.0
    sql = """
    SELECT EXTRACT(EPOCH FROM COALESCE(MAX(sp.updated_at), TO_TIMESTAMP(0))) AS version_ts
    FROM system_preferences sp
    WHERE (
      (%(uid)s IS NULL AND sp.user_id IS NULL)
      OR (%(uid)s IS NOT NULL AND (sp.user_id = (%(uid)s)::uuid OR sp.user_id IS NULL))
    )
    """
    try:
        db = PostgresDB()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"uid": uid})
                row = cur.fetchone()
                if not row:
                    return 0.0
                try:
                    return float(row[0] or 0.0)
                except Exception:
                    return 0.0
    except Exception as e:
        _mark_db_temporarily_unavailable()
        logger.warning(f"读取系统偏好版本失败，将使用回退偏好：{e}")
        return 0.0


def _load_prefs_from_db(user_id: Optional[str]) -> dict[str, Any]:
    uid = _resolve_user_id(user_id)
    if _should_skip_db():
        return {}
    sql = """
    SELECT DISTINCT ON (sp.key)
      sp.key AS key,
      sp.value AS value
    FROM system_preferences sp
    WHERE (
      (%(uid)s IS NULL AND sp.user_id IS NULL)
      OR (%(uid)s IS NOT NULL AND (sp.user_id = (%(uid)s)::uuid OR sp.user_id IS NULL))
    )
    ORDER BY
      sp.key,
      (sp.user_id IS NULL) ASC,
      sp.updated_at DESC
    """
    out: dict[str, Any] = {}
    try:
        db = PostgresDB()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"uid": uid})
                rows = cur.fetchall() or []
                for r in rows:
                    k = str(r[0] or "").strip()
                    if not k:
                        continue
                    out[k] = r[1]
    except Exception as e:
        _mark_db_temporarily_unavailable()
        raise e
    return out


def _get_cached_prefs(user_id: Optional[str]) -> dict[str, Any]:
    uid = _resolve_user_id(user_id)
    now = time.time()
    last_checked = _prefs_cache_checked_at.get(uid, 0.0)
    if (now - last_checked) < _CACHE_CHECK_INTERVAL_SEC and uid in _prefs_cache:
        return _prefs_cache.get(uid, {})

    _prefs_cache_checked_at[uid] = now
    version_ts = _get_prefs_version_ts(uid)
    cached_version = _prefs_cache_version_ts.get(uid, -1.0)
    if uid in _prefs_cache and version_ts == cached_version:
        return _prefs_cache.get(uid, {})

    try:
        prefs = _load_prefs_from_db(uid)
        _prefs_cache[uid] = prefs
        _prefs_cache_version_ts[uid] = version_ts
        return prefs
    except Exception as e:
        logger.warning(f"读取系统偏好失败，将使用回退偏好：{e}")
        return _prefs_cache.get(uid, {})


def _get_cached_db_configs(user_id: Optional[str]) -> dict[str, dict[str, Any]]:
    uid = _resolve_user_id(user_id)
    now = time.time()
    last_checked = _cache_checked_at.get(uid, 0.0)
    if (now - last_checked) < _CACHE_CHECK_INTERVAL_SEC and uid in _cache_configs:
        return _cache_configs.get(uid, {})

    _cache_checked_at[uid] = now
    version_ts = _get_config_version_ts(uid)
    cached_version = _cache_version_ts.get(uid, -1.0)
    if uid in _cache_configs and version_ts == cached_version:
        return _cache_configs.get(uid, {})

    try:
        cfg = _load_configs_from_db(uid)
        _cache_configs[uid] = cfg
        _cache_version_ts[uid] = version_ts
        return cfg
    except Exception as e:
        logger.warning(f"读取 Agent 模型配置失败，将使用回退配置：{e}")
        return _cache_configs.get(uid, {})


def get_agent_config(name: str, *, user_id: Optional[str] = None) -> dict[str, Any]:
    base = dict(DEFAULT_AGENT_CONFIGS.get(name, {}))
    db_cfg = _get_cached_db_configs(user_id).get(name, {})
    base.update({k: v for k, v in db_cfg.items() if v is not None})

    prefs = _get_cached_prefs(user_id)
    lang = _normalize_lang(prefs.get("agent_language"))
    if not lang:
        lang = _normalize_lang(prefs.get("ui_locale"))
    if lang:
        base["language"] = lang

    if not base.get("llm_base_url"):
        base["llm_base_url"] = _default_llm_base_url()
    if not base.get("llm_api_key"):
        base["llm_api_key"] = _default_llm_api_key()
    return base


def get_agent_enabled(*, user_id: Optional[str] = None) -> bool:
    """
    中文注释：Agent 总开关。
    - 优先读取 system_preferences.agent_enabled
    - 若不存在则默认关闭（fail-close），避免配置未完成时误触发工作流/LLM
    """
    env_v = os.getenv("UTAKER_AGENT_ENABLED")
    if env_v is not None:
        b = _normalize_bool(env_v)
        if b is not None:
            return b
    prefs = _get_cached_prefs(user_id)
    b = _normalize_bool(prefs.get("agent_enabled"))
    return bool(b) if b is not None else False


def get_agent_readiness(
    *,
    user_id: Optional[str] = None,
    required_agents: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    中文注释：Agent 就绪态（readiness）用于服务内 gating。
    - DB 配置可用时：要求关键 agents 存在对应的激活模型配置（避免默认模型误跑）
    - DB 配置不可用时：允许使用环境变量默认 LLM 配置兜底
    """
    uid = _resolve_user_id(user_id)
    agents = required_agents or list(REQUIRED_AGENT_NAMES)
    reasons: list[str] = []

    db_required = _db_enabled()
    if db_required:
        db_cfg = _get_cached_db_configs(uid)
        missing = [a for a in agents if not db_cfg.get(a)]
        if missing:
            reasons.append(f"missing_agent_model_configs:{','.join(missing)}")

    base_url_missing: list[str] = []
    api_key_missing: list[str] = []
    model_missing: list[str] = []
    for a in agents:
        cfg = get_agent_config(a, user_id=uid)
        if not str(cfg.get("model_id") or "").strip():
            model_missing.append(a)
        if not str(cfg.get("llm_base_url") or "").strip():
            base_url_missing.append(a)
        if not str(cfg.get("llm_api_key") or "").strip():
            api_key_missing.append(a)

    if model_missing:
        reasons.append(f"missing_model_id:{','.join(model_missing)}")
    if base_url_missing:
        reasons.append(f"missing_llm_base_url:{','.join(base_url_missing)}")
    if api_key_missing:
        reasons.append(f"missing_llm_api_key:{','.join(api_key_missing)}")

    ready = len(reasons) == 0
    return {"ready": ready, "reasons": reasons, "required_agents": agents, "db_required": db_required}


if __name__ == "__main__":
    user_id = "09bcc454-3855-4be1-a5cf-66bdeae42ae0"
    name = "signal_validation"
    print(get_agent_config(name=name, user_id=user_id))
