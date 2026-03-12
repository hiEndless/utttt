from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.execution_service import app as app_module


class _FakeRedis:
    async def get(self, key: str):  # noqa: ANN001
        _ = key
        return None


def test_create_app_reject_unsupported_provider_mode(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("EXECUTION_STATE_PROVIDER_MODE", "invalid")
    try:
        app_module.create_app()
        assert False, "expected RuntimeError for unsupported provider mode"
    except RuntimeError as exc:
        assert "unsupported EXECUTION_STATE_PROVIDER_MODE=invalid" in str(exc)


def test_create_app_use_redis_mode(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("EXECUTION_STATE_PROVIDER_MODE", "redis")
    monkeypatch.setenv("EXECUTION_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(app_module, "create_redis_client_from_env", lambda redis_url=None: _FakeRedis())
    app = app_module.create_app()
    assert app.title == "execution_service"


def test_create_app_use_redis_confidence_metrics_mode(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("EXECUTION_STATE_PROVIDER_MODE", "redis")
    monkeypatch.setenv("EXECUTION_CONFIDENCE_METRICS_MODE", "redis")
    monkeypatch.setenv("EXECUTION_CONFIDENCE_METRICS_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(app_module, "create_redis_client_from_env", lambda redis_url=None: _FakeRedis())
    app = app_module.create_app()
    assert app.title == "execution_service"


def test_create_app_prod_reject_unsupported_provider_mode(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("EXECUTION_RUNTIME_PROFILE", "prod")
    monkeypatch.setenv("EXECUTION_STATE_PROVIDER_MODE", "stub")
    try:
        app_module.create_app()
        assert False, "expected RuntimeError in prod when provider mode is unsupported"
    except RuntimeError as exc:
        assert "unsupported EXECUTION_STATE_PROVIDER_MODE=stub" in str(exc)


def test_create_app_reject_unsupported_sink_mode(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("EXECUTION_STATE_PROVIDER_MODE", "redis")
    monkeypatch.setenv("EXECUTION_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(app_module, "create_redis_client_from_env", lambda redis_url=None: _FakeRedis())
    monkeypatch.setenv("EXECUTION_SUBMIT_ENABLED", "true")
    monkeypatch.setenv("EXECUTION_SINK_MODE", "mock")
    try:
        app_module.create_app()
        assert False, "expected RuntimeError when sink mode is unsupported"
    except RuntimeError as exc:
        assert "unsupported EXECUTION_SINK_MODE=mock" in str(exc)
