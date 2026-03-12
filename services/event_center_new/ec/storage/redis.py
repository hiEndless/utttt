from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Protocol


class RedisClientLike(Protocol):
    def xadd(self, name: str, fields: dict[str, str], maxlen: int | None = None, approximate: bool = True):  # noqa: ANN201
        ...

    def set(self, name: str, value: str):  # noqa: ANN201
        ...


@dataclass(frozen=True)
class RedisLayerStoreConfig:
    raw_stream: str = "ec:raw"
    normalized_stream: str = "ec:normalized"
    evidence_stream: str = "ec:evidence"
    context_stream: str = "ec:context"
    selected_stream: str = "ec:selected"
    maxlen: int = 20000
    approximate: bool = True


class RedisLayerStore:
    """Redis 分层写入适配器。"""

    def __init__(self, *, client: RedisClientLike, cfg: RedisLayerStoreConfig | None = None) -> None:
        self._client = client
        self._cfg = cfg or RedisLayerStoreConfig()

    @classmethod
    def from_url(cls, url: str, cfg: RedisLayerStoreConfig | None = None) -> "RedisLayerStore":
        try:
            import redis  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("未安装 redis 依赖，无法启用 RedisLayerStore") from exc
        client = redis.Redis.from_url(url, decode_responses=True)
        return cls(client=client, cfg=cfg)

    def write_raw(self, payload: dict[str, Any]) -> None:
        self._write(self._cfg.raw_stream, payload)

    def write_normalized(self, payload: dict[str, Any]) -> None:
        self._write(self._cfg.normalized_stream, payload)

    def write_evidence(self, payload: dict[str, Any]) -> None:
        self._write(self._cfg.evidence_stream, payload)

    def write_context(self, payload: dict[str, Any]) -> None:
        self._write(self._cfg.context_stream, payload)

    def write_selected(self, payload: dict[str, Any]) -> None:
        self._write(self._cfg.selected_stream, payload)

    def write_runner_health(self, payload: dict[str, Any], *, key: str = "ec:runner:health") -> None:
        # 中文注释：健康信号走 KV，便于运维侧直接 GET，不需要消费 stream。
        self._client.set(key, json.dumps(payload, ensure_ascii=False))

    def _write(self, stream: str, payload: dict[str, Any]) -> None:
        # 中文注释：统一 JSON 序列化入流，便于后续回放工具按层读取并反序列化。
        fields = {"payload": json.dumps(payload, ensure_ascii=False), "ts_ms": str(payload.get("ts_ms", ""))}
        self._client.xadd(stream, fields, maxlen=self._cfg.maxlen, approximate=self._cfg.approximate)
