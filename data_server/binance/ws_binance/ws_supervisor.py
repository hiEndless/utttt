from __future__ import annotations

import asyncio
import json
import os
import random
import time
from dataclasses import dataclass
from typing import Any, Optional

from data_server.binance.ws_binance.market_ws import BinanceMarketWS, detector, monitor_symbols, on_msg
from data_server.binance.ws_binance.user_ws import BinanceUserWS as BinanceSignedUserWS
from data_server.binance.ws_binance.user_ws import analysis_service, user_callback
from data_server.binance.ws_binance.utils.redis_client import get_async_redis


@dataclass(frozen=True)
class BinanceAccountConfig:
    api_key: str
    api_secret: str


class BinanceWSSupervisor:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()

        self._exchange = "binance"
        self._active_key = "exchange_account:binance:active"

        self._market_ws: Optional[BinanceMarketWS] = None
        self._market_symbols_task: Optional[asyncio.Task] = None
        self._market_started: bool = False

        self._user_ws: Optional[BinanceSignedUserWS] = None
        self._user_task: Optional[asyncio.Task] = None
        self._user_started: bool = False
        self._user_config: Optional[BinanceAccountConfig] = None

        self._redis = get_async_redis()
        self._watch_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

        self._last_active_raw: Optional[str] = None
        self._last_active_ts_ms: Optional[int] = None

    async def bootstrap(self) -> None:
        async with self._lock:
            if not self._market_started:
                await self._start_market_ws()

            if self._watch_task is None:
                self._watch_task = asyncio.create_task(self._watch_active_account_loop())
            if self._heartbeat_task is None:
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def shutdown(self) -> None:
        async with self._lock:
            if self._watch_task:
                self._watch_task.cancel()
                try:
                    await self._watch_task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass
                self._watch_task = None
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
                try:
                    await self._heartbeat_task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass
                self._heartbeat_task = None
            await self._stop_user_ws()
            await self._stop_market_ws()

    async def status(self) -> dict[str, Any]:
        async with self._lock:
            rest_hb = await self._get_heartbeat(f"health:{self._exchange}:rest_binance")
            market_hb = await self._get_heartbeat(f"health:{self._exchange}:market_ws")
            user_hb = await self._get_heartbeat(f"health:{self._exchange}:user_ws")
            return {
                "market_ws": {
                    "running": bool(self._market_started),
                    "health": market_hb,
                },
                "user_ws": {
                    "running": bool(self._user_started),
                    "has_config": bool(self._user_config),
                    "api_key_masked": self._mask_key(self._user_config.api_key) if self._user_config else None,
                    "health": user_hb,
                },
                "rest_binance": {
                    "health": rest_hb,
                },
                "active_key": {
                    "key": self._active_key,
                    "last_seen_at": self._last_active_ts_ms,
                },
            }

    async def reload_from_store(self) -> dict[str, Any]:
        async with self._lock:
            cfg = await self._load_account_config()
            if not cfg:
                await self._apply_account_locked(None, reset_state=True)
                return {"ok": True, "action": "stopped"}
            await self._apply_account_locked(cfg, reset_state=True)
            return {"ok": True, "action": "restarted"}

    async def apply_account(self, api_key: str, api_secret: str, reset_state: bool = True) -> dict[str, Any]:
        cfg = BinanceAccountConfig(api_key=api_key, api_secret=api_secret)
        async with self._lock:
            await self._apply_account_locked(cfg, reset_state=reset_state)
            return {"ok": True, "action": "applied"}

    async def stop_user(self, reset_state: bool = True) -> dict[str, Any]:
        async with self._lock:
            await self._apply_account_locked(None, reset_state=reset_state)
            return {"ok": True, "action": "stopped"}

    async def _apply_account_locked(self, cfg: Optional[BinanceAccountConfig], reset_state: bool) -> None:
        if (
            cfg
            and self._user_config
            and cfg.api_key == self._user_config.api_key
            and cfg.api_secret == self._user_config.api_secret
        ):
            if self._user_started:
                return

        await self._stop_user_ws()
        if reset_state:
            await self._reset_account_state()

        self._user_config = cfg
        if cfg:
            await self._start_user_ws(cfg)

    async def _start_market_ws(self) -> None:
        if self._market_started:
            return
        self._market_ws = BinanceMarketWS(streams=[], on_message=on_msg)
        try:
            if detector is not None:
                await detector.start()
        except Exception:
            pass
        await self._market_ws.start()
        self._market_symbols_task = asyncio.create_task(monitor_symbols(self._market_ws))
        self._market_started = True

    async def _stop_market_ws(self) -> None:
        if self._market_symbols_task:
            self._market_symbols_task.cancel()
            try:
                await self._market_symbols_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
            self._market_symbols_task = None
        if self._market_ws:
            try:
                await self._market_ws.stop()
            except Exception:
                pass
            self._market_ws = None
        try:
            if detector is not None:
                await detector.stop()
        except Exception:
            pass
        self._market_started = False

    async def _start_user_ws(self, cfg: BinanceAccountConfig) -> None:
        if self._user_started:
            return
        self._user_ws = BinanceSignedUserWS(api_key=cfg.api_key, api_secret=cfg.api_secret)
        self._user_ws.register_callback(user_callback)
        self._user_task = asyncio.create_task(self._user_ws.run())
        self._user_started = True

    async def _stop_user_ws(self) -> None:
        if self._user_ws:
            try:
                await self._user_ws.stop()
            except Exception:
                pass
        if self._user_task:
            self._user_task.cancel()
            try:
                await self._user_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
        self._user_ws = None
        self._user_task = None
        self._user_started = False

    async def _reset_account_state(self) -> None:
        # 中文注释：切换账号时需要清理“账号相关”的缓存，避免把 A 账号的持仓与 B 账号混在一起。
        try:
            analysis_service.set_old_data(None)
        except Exception:
            pass
        try:
            await self._redis.delete("positions:binance", "balance:binance")
        except Exception:
            pass
        try:
            await self._redis.delete("symbol:binance")
        except Exception:
            pass

    async def _watch_active_account_loop(self) -> None:
        # 中文注释：常驻 watch 当前交易所 active key 的变化；无配置时静默等待，有变化时自动启停 user_ws。
        poll_s = float(os.getenv("EXCHANGE_ACTIVE_WATCH_INTERVAL_S", "1.0") or "1.0")
        jitter_s = float(os.getenv("EXCHANGE_ACTIVE_WATCH_JITTER_S", "0.2") or "0.2")
        last_raw: Optional[str] = None

        await asyncio.sleep(random.random() * min(1.0, poll_s))

        while True:
            try:
                raw = await self._redis.get(self._active_key)
            except Exception:
                raw = None

            if raw != last_raw:
                last_raw = raw
                async with self._lock:
                    self._last_active_raw = raw
                    self._last_active_ts_ms = int(time.time() * 1000)

                cfg = self._parse_account_config_from_raw(raw)
                try:
                    async with self._lock:
                        await self._apply_account_locked(cfg, reset_state=True)
                except Exception:
                    pass

            await asyncio.sleep(max(0.1, poll_s + random.uniform(-jitter_s, jitter_s)))

    def _parse_account_config_from_raw(self, raw: Optional[str]) -> Optional[BinanceAccountConfig]:
        if not raw:
            return None
        try:
            obj = json.loads(raw)
        except Exception:
            return None
        api_key = str(obj.get("api_key") or "").strip()
        api_secret = str(obj.get("api_secret") or "").strip()
        if not api_key or not api_secret:
            return None
        return BinanceAccountConfig(api_key=api_key, api_secret=api_secret)

    async def _heartbeat_loop(self) -> None:
        # 中文注释：定期写入本进程内 WS 服务心跳，供 internal_api/status 监控。
        interval_s = float(os.getenv("HEALTH_HEARTBEAT_INTERVAL_S", "2.0") or "2.0")
        ttl_s = int(float(os.getenv("HEALTH_HEARTBEAT_TTL_S", "10") or "10"))
        while True:
            ts_ms = int(time.time() * 1000)
            try:
                await self._redis.set(
                    f"health:{self._exchange}:market_ws",
                    json.dumps({"ts": ts_ms, "running": bool(self._market_started)}),
                    ex=ttl_s,
                )
            except Exception:
                pass
            try:
                await self._redis.set(
                    f"health:{self._exchange}:user_ws",
                    json.dumps({"ts": ts_ms, "running": bool(self._user_started)}),
                    ex=ttl_s,
                )
            except Exception:
                pass
            await asyncio.sleep(max(0.5, interval_s))

    async def _get_heartbeat(self, key: str) -> dict[str, Any]:
        try:
            raw = await self._redis.get(key)
        except Exception:
            raw = None
        if not raw:
            return {"alive": False, "ts": None}
        try:
            obj = json.loads(raw)
        except Exception:
            return {"alive": False, "ts": None}
        ts = obj.get("ts")
        try:
            ts_int = int(ts)
        except Exception:
            ts_int = None
        now = int(time.time() * 1000)
        alive = bool(ts_int) and (now - ts_int) <= 15000
        obj["alive"] = alive
        obj["ts"] = ts_int
        return obj

    async def _load_account_config(self) -> Optional[BinanceAccountConfig]:
        # 中文注释：优先从 Redis 读取后端下发的“当前活跃账号”，不存在则回退到环境变量（本地调试场景）。
        try:
            raw = await self._redis.get(self._active_key)
        except Exception:
            raw = None
        cfg = self._parse_account_config_from_raw(raw)
        if cfg:
            return cfg

        api_key = str(os.getenv("BINANCE_API_KEY", "") or "").strip()
        api_secret = str(os.getenv("BINANCE_API_SECRET", "") or "").strip()
        if api_key and api_secret:
            return BinanceAccountConfig(api_key=api_key, api_secret=api_secret)
        return None

    @staticmethod
    def _mask_key(v: str) -> str:
        if not v:
            return ""
        if len(v) <= 8:
            return "*" * len(v)
        return f"{v[:4]}********{v[-4:]}"

