from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any, Awaitable, Callable, Optional

from agent_server.background_main import _run as run_background
from agent_server.final_listen_main import _run as run_final
from agent_server.risk.risk_state_cron import _run as run_risk_cron
from agent_server.utils.agent_status import get_agent_gate_snapshot, update_agent_status_snapshot
from agent_server.utils.redis_client import get_verified_redis_client


logger = logging.getLogger("agent_supervisor")


ServiceRunner = Callable[[asyncio.Event], Awaitable[None]]


class AgentServiceSupervisor:
    def __init__(self, stop_event: Optional[asyncio.Event] = None) -> None:
        self._lock = asyncio.Lock()
        self._stop = stop_event or asyncio.Event()
        self._tasks: dict[str, asyncio.Task] = {}
        self._restart_count: dict[str, int] = {}
        self._last_error: dict[str, str] = {}
        self._last_error_ts_ms: dict[str, int] = {}
        self._hb_task: Optional[asyncio.Task] = None

        self._services: dict[str, ServiceRunner] = {
            "background": run_background,
            "final_listener": run_final,
            "risk_cron": run_risk_cron,
        }

    async def bootstrap(self) -> None:
        async with self._lock:
            for name, runner in self._services.items():
                self._ensure_task_locked(name, runner)
            if self._hb_task is None:
                self._hb_task = asyncio.create_task(self._heartbeat_loop(), name="agent_supervisor_heartbeat")

    async def shutdown(self) -> None:
        async with self._lock:
            self._stop.set()
            if self._hb_task:
                self._hb_task.cancel()
                await asyncio.gather(self._hb_task, return_exceptions=True)
                self._hb_task = None

            for name, task in list(self._tasks.items()):
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                del self._tasks[name]

    async def status(self) -> dict[str, Any]:
        async with self._lock:
            out: dict[str, Any] = {}
            for name, task in self._tasks.items():
                out[name] = {
                    "running": bool(task and not task.done()),
                    "restart_count": int(self._restart_count.get(name, 0)),
                    "last_error": self._last_error.get(name),
                    "last_error_ts_ms": self._last_error_ts_ms.get(name),
                }
            return out

    def stop_event(self) -> asyncio.Event:
        return self._stop

    def _ensure_task_locked(self, name: str, runner: ServiceRunner) -> None:
        t = self._tasks.get(name)
        if t and not t.done():
            return

        task = asyncio.create_task(runner(self._stop), name=f"agent_service:{name}")

        def _done_cb(done_task: asyncio.Task) -> None:
            if self._stop.is_set():
                return
            try:
                exc = done_task.exception()
            except asyncio.CancelledError:
                return
            except Exception as e:
                exc = e

            if exc is None:
                self._schedule_restart(name, runner, reason="exited")
                return

            self._last_error[name] = str(exc)
            self._last_error_ts_ms[name] = int(time.time() * 1000)
            logger.error("service_crashed: %s: %s", name, exc, exc_info=exc)
            self._schedule_restart(name, runner, reason="crashed")

        task.add_done_callback(_done_cb)
        self._tasks[name] = task

    def _schedule_restart(self, name: str, runner: ServiceRunner, *, reason: str) -> None:
        self._restart_count[name] = int(self._restart_count.get(name, 0)) + 1
        attempt = self._restart_count[name]
        base = min(30.0, 0.5 * (2 ** min(6, attempt)))
        delay = max(0.5, base + random.random() * 0.3)
        asyncio.create_task(self._restart_after(name, runner, delay_s=delay, reason=reason), name=f"restart:{name}")

    async def _restart_after(self, name: str, runner: ServiceRunner, *, delay_s: float, reason: str) -> None:
        try:
            await asyncio.sleep(delay_s)
        except asyncio.CancelledError:
            return
        if self._stop.is_set():
            return
        async with self._lock:
            self._ensure_task_locked(name, runner)
        logger.warning("service_restarted: %s reason=%s delay_s=%.2f", name, reason, delay_s)

    async def _heartbeat_loop(self) -> None:
        redis = None
        try:
            redis = await get_verified_redis_client()
        except Exception:
            redis = None

        while not self._stop.is_set():
            try:
                enabled, ready, reasons = await get_agent_gate_snapshot(user_id=None)
                extra = await self.status()
                if redis is not None:
                    await update_agent_status_snapshot(
                        redis,
                        module="supervisor",
                        user_id=None,
                        enabled=enabled,
                        ready=ready,
                        reasons=reasons,
                        extra={"services": extra},
                    )
            except Exception:
                pass
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                pass
