from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from execution_service import app as app_module


class _FakeRedis:
    async def get(self, key: str):  # noqa: ANN001
        _ = key
        return None


def test_create_app_use_stub_mode(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("EXECUTION_STATE_PROVIDER_MODE", "stub")
    app = app_module.create_app()
    assert app.title == "execution_service"


def test_create_app_use_redis_mode(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("EXECUTION_STATE_PROVIDER_MODE", "redis")
    monkeypatch.setenv("EXECUTION_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(app_module, "create_redis_client_from_env", lambda redis_url=None: _FakeRedis())
    app = app_module.create_app()
    assert app.title == "execution_service"
