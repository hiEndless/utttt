import os
import sys
import json
import asyncio
import redis
from typing import List, Set
from event_center.config import cfg
from event_center.indicators_event.engine.event_engine import run_event_engine
from event_center.pipeline.raw_event import build_raw_event
import time


def _redis_client(db: int | None = None) -> redis.Redis:
    return redis.Redis(
        host=cfg.redis_host,
        port=cfg.redis_port,
        db=(db if db is not None else cfg.redis_db),
        password=(cfg.redis_password or None),
        decode_responses=True,
    )


def load_symbols(client: redis.Redis, exchange: str) -> List[str]:
    # 兼容两种写入方命名：
    # - market_ws 目前写的是 `symbol:{exchange}`（单数）
    # - 旧逻辑/部分模块可能写的是 `symbols:{exchange}`（复数）
    # 这里优先读单数，避免一直拿不到交易对导致休眠。
    key = f"symbol:{exchange}"
    try:
        members = client.smembers(key)
        if members:
            return sorted(list(members))
        val = client.get(key)
        if val:
            try:
                data = json.loads(val)
                if isinstance(data, list):
                    return sorted([str(x) for x in data])
                if isinstance(data, dict):
                    return sorted([str(k) for k in data.keys()])
            except Exception:
                parts = [p.strip() for p in val.split(",") if p.strip()]
                if parts:
                    return sorted(parts)
    except Exception:
        pass

    # fallback: 读取复数 key
    fallback_key = f"symbols:{exchange}"
    try:
        members = client.smembers(fallback_key)
        if members:
            return sorted(list(members))
    except Exception:
        pass

    discovered: Set[str] = set()
    try:
        pattern = f"indicators:{exchange}:*:" + "1m"
        for k in client.scan_iter(pattern):
            try:
                parts = k.split(":")
                if len(parts) >= 4:
                    symbol = parts[2]
                    if symbol:
                        discovered.add(symbol)
            except Exception:
                continue
    except Exception:
        pass
    return sorted(list(discovered))


def _extract_plugin_evidence(res: dict):
    """
    从 scores / factors 中提取最小可解释插件证据
    - single_signal → single_signal_<indicator>
    """
    def _infer_family(name: str, src: str | None) -> str:
        n = (name or "").lower()
        s = (src or "").lower()
        for kw in ["macd", "ema", "ma", "boll", "williams", "rsi", "kdj", "atr"]:
            if kw in n or kw in s:
                return kw
        return "unknown"
    # 1️⃣ 先从 factors 建立 (plugin, tf) -> src 映射
    factor_src_map = {}
    for f in res.get("factors") or []:
        pname = f.get("plugin")
        tf = f.get("tf")
        src = f.get("src")
        if pname and tf and src:
            factor_src_map[(pname, tf)] = src

    # 2️⃣ 聚合 scores
    # 2️⃣ 先按 (name, tf) 聚合，保留该(name, tf)的最大绝对值score
    per_name_tf = {}
    for s in res.get("scores") or []:
        pname = s.get("plugin")
        tf = s.get("tf")
        if not pname or not tf:
            continue
        # single_signal 指标细分
        src = factor_src_map.get((pname, tf), None)
        if pname == "single_signal":
            ind = src or "unknown"
            pname = f"single_signal_{ind}"
        key = (pname, tf)
        cur = per_name_tf.get(key)
        sc = float(s.get("score") or 0.0)
        if (cur is None) or (abs(sc) > abs(cur["score"])):
            per_name_tf[key] = {
                "name": pname,
                "tf": tf,
                "cls": s.get("cls"),
                "score": sc,
                "src": src,
                "is_combo": ("combo" in (pname or "").lower()),
            }

    # 3️⃣ 同一 tf + 同一指标族，仅保留“最强代表”；优先选择 combo，其次绝对值最大
    by_tf_family = {}
    for rec in per_name_tf.values():
        fam = _infer_family(rec["name"], rec.get("src"))
        key = (rec["tf"], fam)
        cand = by_tf_family.get(key)
        def better(a, b):
            if a["is_combo"] and not b["is_combo"]:
                return True
            if (not a["is_combo"]) and b["is_combo"]:
                return False
            return abs(a["score"]) > abs(b["score"])
        if (cand is None) or better(rec, cand):
            by_tf_family[key] = rec

    # 4️⃣ 汇总为 plugins：按 name 合并 tfs，score 取该name下最大绝对值
    plugins = {}
    for rec in by_tf_family.values():
        name = rec["name"]
        item = plugins.setdefault(
            name,
            {"name": name, "cls": rec.get("cls"), "tfs": set(), "score": 0.0},
        )
        item["tfs"].add(rec["tf"])
        if abs(rec["score"]) > abs(item["score"]):
            item["score"] = rec["score"]

    out = []
    for p in plugins.values():
        p["tfs"] = sorted(p["tfs"])
        out.append(p)
    return out


async def _run_one(symbol: str, exchange: str, client: redis.Redis):
    try:
        res = await asyncio.to_thread(run_event_engine, symbol, exchange, client)

        print(
            f"[指标事件] 交易所={exchange} 交易对={symbol} "
            f"市场状态={res.get('market_state')} "
            f"方向={res.get('direction')} "
            f"强度={res.get('signal_strength')}"
        )

        # ====== 过滤条件（保持你原来的逻辑） ======
        band_order = {"weak": 1, "medium": 2, "strong": 3}
        min_band = os.getenv("ENGINE_MIN_BAND", "medium").lower()
        min_band_val = band_order.get(min_band, 2)
        band_val = band_order.get(
            str(res.get("signal_strength_band") or "weak").lower(), 1
        )

        meta = res.get("meta", {}) or {}
        align = meta.get("timeframe_alignment", {}) or {}
        align_depth = len(align.get(res.get("direction"), []))
        req_align = int(os.getenv("ENGINE_REQUIRE_ALIGNMENT_COUNT", "1"))

        if os.getenv("ENGINE_EXCLUDE_CONFLICT", "true").lower() == "true":
            if res.get("market_state") == "conflict":
                print(f"[指标事件] 跳过写入 原因=conflict 交易所={exchange} 交易对={symbol}")
                return

        if band_val < min_band_val:
            print(f"[指标事件] 跳过写入 原因=band({band_val}<{min_band_val}) 交易所={exchange} 交易对={symbol}")
            return
        if align_depth < req_align:
            print(f"[指标事件] 跳过写入 原因=alignment({align_depth}<{req_align}) 交易所={exchange} 交易对={symbol}")
            return

        # ====== 构造 Raw Payload（三层） ======
        # 说明：
        # - summary.signal_strength：引擎“最终强度”，已包含同类去重、同TF跨类折扣、分桶聚合、
        #   冲突桶定向降级、（可选）跨TF同类衰减与动态中性区间判定，用于决定direction/level
        # - structure.raw_total：结构“基线强度”，仅做同TF同类去重 + 同TF跨类折扣 + 分桶聚合，
        #   未应用冲突降级与跨TF同类衰减，主要用于解释与审计

        plugins_evd = _extract_plugin_evidence(res)
        # 选择代表插件及其主周期
        top_plugin = None
        if plugins_evd:
            top_plugin = max(plugins_evd, key=lambda p: abs(float(p.get("score") or 0.0)))
        primary_tf = ""
        if top_plugin:
            tfs_list = top_plugin.get("tfs") or []
            if tfs_list:
                primary_tf = str(tfs_list[0])
        payload = {
            # -------- summary（快速结论） --------
            "summary": {
                "direction": res.get("direction"),
                "market_state": res.get("market_state"),
                "signal_strength": res.get("signal_strength"),
                "signal_strength_band": res.get("signal_strength_band"),
                "level": res.get("level"),
                "plugin": (top_plugin.get("name") if top_plugin else ""),
                "primary_tf": primary_tf,
            },

            # -------- structure（L0 / L1 依据） --------
            "structure": {
                "raw_total": meta.get("raw_total"),
                "bucket_dirs": meta.get("bucket_dirs"),
                "timeframe_alignment": meta.get("timeframe_alignment"),
                "divergence": meta.get("divergence"),
                "final_forbidden": meta.get("final_forbidden"),
            },

            # -------- evidence（最小可解释证据） --------
            "evidence": {
                "plugins": plugins_evd,
                "factor_count": len(res.get("factors") or []),
            },
        }

        ts_ms = int(time.time() * 1000)

        # 事件类型改为来源于factors的插件名（取同族代表后的最强者）
        event_type_name = (top_plugin.get("name") if top_plugin else "tech.engine")

        raw = build_raw_event(
            exchange=exchange,
            symbol=symbol,
            account_id=f"{exchange}_public",
            source="ind_event_engine",
            event_class="technical",
            event_type=event_type_name,
            event_level=int(res.get("level") or 1),
            timestamp_ms=ts_ms,
            payload=payload,
        )

        client.xadd(cfg.raw_stream, raw)
        # print(raw)
        print(
            f"[指标事件] 已写入 Raw 流={cfg.raw_stream} "
            f"交易所={exchange} 交易对={symbol} 等级={raw.get('event_level')}"
        )

    except Exception as e:
        print(f"[指标事件] 执行出错 交易所={exchange} 交易对={symbol} 错误={e}")


async def run_loop(exchange: str, poll_sec: int = 60, concurrency: int = 16):
    client = _redis_client()
    sem = asyncio.Semaphore(max(1, concurrency))
    while True:
        try:
            symbols = load_symbols(client, exchange)
            if not symbols:
                print(f"[指标事件] 未发现交易对 交易所={exchange} 即将休眠 {poll_sec} 秒")
                await asyncio.sleep(poll_sec)
                continue
            tasks = []
            for sym in symbols:
                async def _task(s=sym):
                    async with sem:
                        await _run_one(s, exchange, client)
                tasks.append(asyncio.create_task(_task()))
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            print(f"[指标事件] 调度循环异常 交易所={exchange} 错误={e}")
        await asyncio.sleep(poll_sec)


if __name__ == "__main__":
    ex = "binance"
    if len(sys.argv) >= 2 and sys.argv[1].strip():
        ex = sys.argv[1].strip()
    poll = int(os.getenv("IND_EVENT_POLL_SEC", "60"))
    conc = int(os.getenv("IND_EVENT_CONCURRENCY", "16"))
    asyncio.run(run_loop(ex, poll_sec=poll, concurrency=conc))
