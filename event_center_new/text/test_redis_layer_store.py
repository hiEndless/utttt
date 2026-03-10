from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from event_center_new.ec.storage.redis import RedisLayerStore, RedisLayerStoreConfig


class _FakeRedis:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.kv_calls: list[dict[str, str]] = []

    def xadd(self, name: str, fields: dict[str, str], maxlen: int | None = None, approximate: bool = True):  # noqa: ANN201
        self.calls.append(
            {
                "name": name,
                "fields": dict(fields),
                "maxlen": maxlen,
                "approximate": approximate,
            }
        )
        return "1-0"

    def set(self, name: str, value: str):  # noqa: ANN201
        self.kv_calls.append({"name": name, "value": value})
        return True


def test_redis_layer_store_writes_all_layers() -> None:
    fake = _FakeRedis()
    store = RedisLayerStore(client=fake)
    payload = {"ts_ms": 123, "asset": "ETHUSDT"}
    store.write_raw(payload)
    store.write_normalized(payload)
    store.write_evidence(payload)
    store.write_context(payload)
    store.write_selected(payload)
    assert [c["name"] for c in fake.calls] == ["ec:raw", "ec:normalized", "ec:evidence", "ec:context", "ec:selected"]
    assert all(c["fields"]["ts_ms"] == "123" for c in fake.calls)


def test_redis_layer_store_uses_custom_streams() -> None:
    fake = _FakeRedis()
    cfg = RedisLayerStoreConfig(
        raw_stream="x:raw",
        normalized_stream="x:norm",
        evidence_stream="x:evd",
        context_stream="x:ctx",
        selected_stream="x:sel",
        maxlen=99,
        approximate=False,
    )
    store = RedisLayerStore(client=fake, cfg=cfg)
    store.write_selected({"ts_ms": 9, "a": 1})
    call = fake.calls[0]
    assert call["name"] == "x:sel"
    assert call["maxlen"] == 99
    assert call["approximate"] is False


def test_redis_layer_store_writes_runner_health_key() -> None:
    fake = _FakeRedis()
    store = RedisLayerStore(client=fake)
    store.write_runner_health({"heartbeat": 1, "error_count": 0}, key="ec:test:health")
    assert len(fake.kv_calls) == 1
    assert fake.kv_calls[0]["name"] == "ec:test:health"
    assert "\"heartbeat\": 1" in fake.kv_calls[0]["value"]
