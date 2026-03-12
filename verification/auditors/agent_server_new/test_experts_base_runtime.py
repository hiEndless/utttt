import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.experts.base.expert_runner import ExpertRunConfig, ExpertRunner
from services.agent_server_new.experts.base.prompt_builder import PromptBuilder
from services.agent_server_new.experts.base.structured_output import StructuredOutput, parse_with_validator


def test_prompt_builder_template_success() -> None:
    pb = PromptBuilder(
        templates={
            "signal.eval.v1": {
                "required_vars": "symbol,direction",
                "system": "You are trader for {symbol}",
                "user": "direction={direction}",
            }
        }
    )
    p = pb.build(template_id="signal.eval.v1", variables={"symbol": "ETHUSDT", "direction": "long"})
    assert "ETHUSDT" in p.system
    assert "long" in p.user
    assert p.meta["template_registered"] is True


def test_prompt_builder_template_missing_vars_raises() -> None:
    pb = PromptBuilder(templates={"t1": {"required_vars": "a,b", "system": "{a}", "user": "{b}"}})
    try:
        pb.build(template_id="t1", variables={"a": 1})
        assert False, "expected ValueError when template vars are missing"
    except ValueError as exc:
        assert "missing template vars" in str(exc)


def test_parse_with_validator_accepts_json_string() -> None:
    out = parse_with_validator('{"x": 1}', validator=lambda x: {"x": int(dict(x)["x"])})
    assert out.valid is True
    assert out.parsed["x"] == 1


def test_parse_with_validator_returns_error_type() -> None:
    out = parse_with_validator({"x": "bad"}, validator=lambda x: int(dict(x)["x"]))
    assert out.valid is False
    assert out.errors is not None
    assert out.errors.get("type")


def test_expert_runner_retries_until_valid() -> None:
    calls = {"n": 0}

    async def _call_model(prompt, cfg):  # noqa: ANN001
        _ = (prompt, cfg)
        calls["n"] += 1
        if calls["n"] < 2:
            return {"ok": False}
        return {"ok": True, "score": 0.9}

    def _parse(raw):  # noqa: ANN001
        payload = dict(raw or {})
        if not payload.get("ok"):
            return StructuredOutput(raw=raw, parsed=None, valid=False, errors={"error": "invalid"})
        return StructuredOutput(raw=raw, parsed=payload, valid=True, errors=None)

    runner = ExpertRunner(config=ExpertRunConfig(model="gpt", max_retries=2))
    prompt = PromptBuilder().build(template_id="adhoc", variables={"system": "s", "user": "u"})
    out = asyncio.run(runner.run(prompt=prompt, call_model=_call_model, parse_output=_parse))
    assert out.valid is True
    assert calls["n"] == 2
