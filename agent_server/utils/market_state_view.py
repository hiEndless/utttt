# market state信息裁剪脚本（兜底脚本），首选agent_context

from typing import Any, Dict, List
import json


def _drop_raw_trends(ms: Dict[str, Any]) -> Dict[str, Any]:
    market_state = ms.get("market_state") or {}
    for k, v in market_state.items():
        if isinstance(v, dict) and "_raw_trends" in v:
            v.pop("_raw_trends", None)
    return ms


def _get_by_path(obj: Dict[str, Any], path: str) -> Any:
    cur: Any = obj
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


def _set_by_path(out: Dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cur = out
    for p in parts[:-1]:
        nxt = cur.get(p)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[p] = nxt
        cur = nxt
    cur[parts[-1]] = value


def _build_view(full: Dict[str, Any], paths: List[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"symbol": full.get("symbol"), "ts": full.get("ts")}
    for path in paths:
        val = _get_by_path(full, path)
        if val is not None:
            _set_by_path(out, path, val)
    return _drop_raw_trends(out)


PROFILES: Dict[str, List[str]] = {
    "force_stats": [
        "market_state.micro_term.state",
        "market_state.short_term.direction",
        "market_state.short_term.risk",
        "market_state.short_term.confidence",
        "market_state.mid_term.direction",
        "market_state.long_term.veto",
        "crowd_state.bias",
        "crowd_state.crowding_level",
        "crowd_state.fragility",
        "crowd_state.consistency",
        "crowd_state.funding_pressure",
    ],
    "kline_expert": [
        "market_state.micro_term.state",
    ],
    "market_structure": [
        "market_state.long_term.veto",
    ],
    "full": [
    ],
}


def set_context_profile(agent: str, paths: List[str], overwrite: bool = True) -> None:
    key = (agent or "").strip().lower()
    if overwrite or key not in PROFILES:
        PROFILES[key] = list(paths or [])
    else:
        PROFILES[key] = list(set(PROFILES[key] + list(paths or [])))


def tailor_market_state_for_agent(agent: str, full: Dict[str, Any]) -> Dict[str, Any]:
    key = (agent or "").strip().lower()
    if key == "full":
        clean = json.loads(json.dumps(full or {}))
        return _drop_raw_trends(clean)
    paths = PROFILES.get(key)
    if not paths:
        clean = json.loads(json.dumps(full or {}))
        return _drop_raw_trends(clean)
    return _build_view(full or {}, paths)


if __name__ == "__main__":
    import json
    import asyncio
    import os
    import sys

    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from agent_server.utils.http_client import http_client
    from agent_server.config import settings

    API_KLINE_READ = "/market_state/read_full"

    async def run():
        url = settings.api_base_url.rstrip("/") + API_KLINE_READ
        payload = {"exchange": "binance", "symbol": "BTCUSDT"}

        try:
            res = await http_client.request("POST", url, json=payload)
            data = (res or {}).get("data") if isinstance(res, dict) else None
            print(json.dumps(data, ensure_ascii=False))
            ctx = tailor_market_state_for_agent("force_stats", data)
            print(json.dumps(ctx, ensure_ascii=False))
        finally:
            await http_client.close()


    asyncio.run(run())