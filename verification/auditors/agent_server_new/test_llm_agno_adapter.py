import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.adapters.llm_agno import AgnoLLMObserver
from services.agent_server_new.runtime.llm_runtime import LLMRuntimeConfig


class _FakeMetrics:
    def __init__(self, *, input_tokens=0, output_tokens=0, total_tokens=0):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = total_tokens


class _FakeRunOut:
    def __init__(self, *, content, metrics=None):  # noqa: ANN001
        self.content = content
        self.metrics = metrics


class _FakeAgent:
    def __init__(self, scripted):  # noqa: ANN001
        self._scripted = scripted

    def run(self, _input):  # noqa: ANN001
        event = self._scripted.pop(0)
        if isinstance(event, Exception):
            raise event
        return event


def test_agno_llm_observer_success_with_string_content() -> None:
    scripted = [_FakeRunOut(content='{"signal_verdict":"accept"}', metrics=_FakeMetrics(input_tokens=10, output_tokens=5, total_tokens=15))]
    obs = AgnoLLMObserver(
        model_id="gpt-4o-mini",
        api_key="sk-test",
        retry_max=0,
        agent_factory=lambda **kwargs: _FakeAgent(scripted),  # noqa: ARG005
    )
    out = asyncio.run(obs.observe({"symbol": "ETHUSDT"}))
    assert out["status"] == "ok"
    assert out["provider"] == "agno"
    assert out["model"] == "gpt-4o-mini"
    assert out["raw_content"] == '{"signal_verdict":"accept"}'
    assert out["usage"] == {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}


def test_agno_llm_observer_stringifies_dict_content() -> None:
    scripted = [_FakeRunOut(content={"signal_verdict": "accept", "signal_direction": "long"})]
    obs = AgnoLLMObserver(
        model_id="gpt-4o-mini",
        api_key="sk-test",
        retry_max=0,
        agent_factory=lambda **kwargs: _FakeAgent(scripted),  # noqa: ARG005
    )
    out = asyncio.run(obs.observe({"symbol": "ETHUSDT"}))
    assert '"signal_verdict": "accept"' in out["raw_content"]


def test_agno_llm_observer_retries_then_success() -> None:
    scripted = [RuntimeError("boom"), _FakeRunOut(content='{"ok":true}')]
    obs = AgnoLLMObserver(
        model_id="gpt-4o-mini",
        api_key="sk-test",
        retry_max=1,
        retry_backoff_s=0.0,
        agent_factory=lambda **kwargs: _FakeAgent(scripted),  # noqa: ARG005
    )
    out = asyncio.run(obs.observe({"symbol": "ETHUSDT"}))
    assert out["status"] == "ok"
    assert out["raw_content"] == '{"ok":true}'


def test_agno_llm_observer_from_env() -> None:
    cfg = LLMRuntimeConfig(
        enabled=True,
        provider="openai_compatible",
        model_id="gpt-4o-mini",
        base_url="http://unit.test/v1",
        api_key="sk-test",
        api_key_env_name="",
        ready=True,
    )
    obs = AgnoLLMObserver.from_env(config=cfg)
    assert obs._model_id == "gpt-4o-mini"  # noqa: SLF001
    assert obs._api_key == "sk-test"  # noqa: SLF001
