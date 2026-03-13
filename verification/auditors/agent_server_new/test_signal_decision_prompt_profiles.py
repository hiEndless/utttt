import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.domain.signal_decision_prompt_profiles import (
    load_signal_decision_prompt_profiles_from_env,
    reset_signal_decision_prompt_profiles_cache,
    validate_signal_decision_prompt_profiles,
)


def test_signal_decision_prompt_profiles_load_from_env(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    cfg = tmp_path / "prompt_profiles.json"
    cfg.write_text(
        json.dumps(
            {
                "generic": {"focus": "generic_v2", "checklist": ["a"], "avoid": ["b"]},
                "onchain": {"focus": "onchain_v2", "checklist": ["wallet"], "avoid": ["noise"]},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_SIGNAL_DECISION_PROMPT_CONFIG_FILE", str(cfg))
    reset_signal_decision_prompt_profiles_cache()
    out = load_signal_decision_prompt_profiles_from_env()
    assert str((out.get("onchain") or {}).get("focus") or "") == "onchain_v2"
    assert str((out.get("technical") or {}).get("focus") or "") == "technical_signal_validation"


def test_signal_decision_prompt_profiles_validate_rejects_unknown_key() -> None:
    cfg = {
        "generic": {"focus": "generic", "checklist": [], "avoid": []},
        "custom_unknown": {"focus": "x", "checklist": [], "avoid": []},
    }
    try:
        validate_signal_decision_prompt_profiles(
            cfg,
            allowed_agent_keys={"technical", "liquidation", "onchain", "social_news", "generic"},
        )
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "非法 agent_key" in str(exc)
