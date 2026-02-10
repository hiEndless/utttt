"""
全局账户风控状态（跟随事件分析一起落库）

后续做全账户熔断、账户级风险模式切换、极端异常保护时再使用account_risk_state
目前account_risk_state先占位

它是：
多个 execution_state 的 收敛结果
只会 收紧，不会放松
不做行情判断、不做仓位分析

读取：
execution_state（全部仓位）
Global Overlay（上一次）
account_risk_state（占位，下次迭代使用，熔断专用）

用于：
Signal Validation Agent（信号确认）：判断“这个信号，在当前账户风险环境下，是否还值得被执行”
任何开仓类 agent
Order Executor / Trade Router（执行层）：校验账户级是否允许
"""

import argparse
import asyncio
import json
from typing import List, Dict, Optional
import time
from agent_server.risk.execution_state_aggregator import age_execution_state
from agent_server.utils.redis_client import get_verified_redis_client
from redis.asyncio import Redis

RISK_REGIME_RANK = {
    "normal": 0,
    "elevated": 1,
    "critical": 2
}


import logging

logger = logging.getLogger(__name__)


def now_ts() -> int:
    """返回当前 Unix 时间戳（秒）。"""
    return int(time.time())


def aggregate_global_overlay(
        execution_states: List[Dict],
        account_risk_state: Dict,
        prev_global_overlay_state: Optional[Dict] = None,
        current_ts: Optional[int] = None
) -> Dict:
    """
    Global Overlay v1 (最小可行版本)

    参数
    ----------
    execution_states : List[Dict]
        逐仓位执行状态列表，例如：
        [
          {
            "symbol": "ETHUSDT",
            "execution_state": {
              "risk_regime": "elevated",
              "action_allowance": {...},
              "cooldown_state": {...}
            }
          }
        ]

    account_risk_state : Dict
        账户级风险快照（余额、可用比例等）
        注意：v1 不主动基于此进行门控，仅保留接口。

    prev_global_overlay_state : Optional[Dict]
        上一个全局叠加层状态（如果存在），仅用于防止冷却状态反复跳变。

    current_ts : Optional[int]
        当前时间戳（秒）。默认为 now()。
    """

    if not execution_states:
        # 如果没有执行状态，返回一个默认的安全状态，而不是报错
        # 允许空状态下的初始化
        execution_states = []

    current_ts = current_ts or now_ts()

    # --------------------------------------------------
    # 0. 结构准备（为 v2/v3 预留）
    # --------------------------------------------------
    risk_sources = {
        "positions": execution_states,
        "account": account_risk_state
    }

    # --------------------------------------------------
    # 1. 聚合全局风险体制（最大值原则）
    # --------------------------------------------------

    # 来源 A：仓位
    position_risk_regime = "normal"
    if risk_sources["positions"]:
        position_risk_regime = max(
            risk_sources["positions"],
            key=lambda x: RISK_REGIME_RANK.get(
                x.get("execution_state", {}).get("risk_regime", "normal"), 0
            )
        ).get("execution_state", {}).get("risk_regime", "normal")

    # 来源 B：账户（v2 占位符）
    # 例如：如果 account_risk_state.get("margin_level") < 1.1: return "critical"
    account_risk_regime = "normal"

    # 最终聚合：max(仓位, 账户)
    global_risk_regime = max(
        [position_risk_regime, account_risk_regime],
        key=lambda x: RISK_REGIME_RANK.get(x, 0)
    )

    # --------------------------------------------------
    # 2. 聚合操作权限（保守的“与”逻辑）
    # --------------------------------------------------
    # 如果没有执行状态，默认为允许（因为未知限制）
    if not risk_sources["positions"]:
        allow_open = True
        allow_add = True
    else:
        allow_open = all(
            es.get("execution_state", {}).get("action_allowance", {}).get("allow_open", False)
            for es in risk_sources["positions"]
        )

        allow_add = all(
            es.get("execution_state", {}).get("action_allowance", {}).get("allow_add", False)
            for es in risk_sources["positions"]
        )

    # 全局叠加层绝不阻止降低风险/退出操作
    global_action_allowance = {
        "allow_open": allow_open,
        "allow_add": allow_add,
        "allow_hold": True,
        "allow_reduce": True,
        "allow_close": True
    }

    # --------------------------------------------------
    # 3. 聚合冷却状态（仅继承）
    # --------------------------------------------------
    cooldown_until_candidates = []

    for es in risk_sources["positions"]:
        cd = es.get("execution_state", {}).get("cooldown_state", {})
        if cd.get("in_cooldown"):
            cooldown_until_candidates.append(cd.get("until_ts", 0))

    computed_in_cooldown = len(cooldown_until_candidates) > 0
    computed_until_ts = (
        max(cooldown_until_candidates)
        if cooldown_until_candidates else None
    )

    # --------------------------------------------------
    # 4. 合并先前的全局叠加层（防止状态反复跳变）
    # --------------------------------------------------
    # 只在仍有活跃冷却候选者时继承冷却
    # 防止“幽灵冷却”，即所有仓位退出冷却后全局冷却仍然持续
    
    cooldown_source = "none"
    if computed_in_cooldown:
        cooldown_source = "derived"

    if prev_global_overlay_state and cooldown_until_candidates:
        prev_cd = prev_global_overlay_state.get("global_cooldown_state", {})
        if prev_cd.get("in_cooldown"):
            # 如果之前有冷却，且当前计算也有冷却候选者，则尝试继承/延长
            computed_in_cooldown = True
            
            # 合并逻辑：取当前计算的截止时间和先前截止时间的最大值
            current_max = computed_until_ts if computed_until_ts is not None else 0
            prev_max = prev_cd.get("until_ts", 0)
            
            if prev_max > current_max:
                computed_until_ts = prev_max
                cooldown_source = "inherited"
            else:
                computed_until_ts = current_max
                # source remains "derived" or derived wins

    global_cooldown_state = {
        "in_cooldown": computed_in_cooldown,
        "until_ts": computed_until_ts
    }

    # --------------------------------------------------
    # 5. 最终全局叠加状态
    # --------------------------------------------------
    return {
        "global_risk_regime": global_risk_regime,
        "global_action_allowance": global_action_allowance,
        "global_cooldown_state": global_cooldown_state,
        "meta": {
            # "derived_from": [es.get("symbol") for es in execution_states],
            "updated_at": current_ts,
            "cooldown_source": cooldown_source
        }
    }


def execution_key(exchange: str) -> str:
    # 中文注释：逐仓位 execution_state 的“目录前缀”，具体 key 允许按 symbol/trade_id 扩展
    return f"risk:execution:{(exchange or '').lower()}"


def global_key(exchange: str) -> str:
    # 中文注释：账户级 global overlay 的唯一 key
    return f"risk:global:{(exchange or '').lower()}"


def _try_infer_symbol_from_key(redis_key: str) -> str | None:
    parts = (redis_key or "").split(":")
    if len(parts) >= 4 and parts[0] == "risk" and parts[1] == "execution":
        sym = parts[3]
        return sym or None
    return None


async def _read_and_maintain_execution_states(exchange: str, redis_client: Optional[Redis] = None) -> List[Dict]:
    """
    从 Redis 读取当前交易所下的所有逐仓位 execution_state。
    同时进行“维护”操作：
    1. 续期 TTL（保证常驻）。
    2. 执行状态老化（Aging）：检查冷却过期、风控等级降级。
    3. 如果状态发生变化，写回 Redis。
    
    兼容两种存储形态：
    1) 多个 string key：risk:execution:{exchange}:* (主要路径)
    2) 单个 hash key：risk:execution:{exchange}（field->json） (Legacy, not actively maintained here)
    """
    r = redis_client or await get_verified_redis_client()
    prefix_key = execution_key(exchange)
    now = now_ts()

    execution_states: List[Dict] = []

    # 1. Handle Legacy Hash (Read-only, no maintenance logic applied to hash fields individually for now)
    # (处理旧版 Hash（只读，目前不逐个字段应用维护逻辑）)
    # 如果我们要维护 Hash，需要回写 HSET。假设 String Key 是新标准。
    hash_updates = {}
    try:
        t = await r.type(prefix_key)
    except Exception:
        t = None

    if t in ("hash", b"hash"):
        items = await r.hgetall(prefix_key)
        for field, raw in (items or {}).items():
            try:
                if isinstance(raw, (bytes, bytearray)):
                    raw = raw.decode("utf-8")
                payload = json.loads(raw) if raw else None
                if isinstance(payload, dict):
                    # --- Hash 的维护逻辑 ---
                    # 1. 老化
                    new_payload = age_execution_state(payload, now_ts=now)
                    
                    # 2. 检查变更
                    content_changed = (
                        new_payload.get("execution_state") != payload.get("execution_state")
                    )
                    
                    if content_changed:
                        # 准备回写
                        if isinstance(field, (bytes, bytearray)):
                            field = field.decode("utf-8")
                        hash_updates[field] = json.dumps(new_payload, ensure_ascii=False)

                    execution_states.append(new_payload)
            except Exception as e:
                logger.debug(f"维护 execution_state hash 字段={field} 失败: {e}")
                continue

    if hash_updates:
        try:
            await r.hset(prefix_key, mapping=hash_updates)
        except Exception as e:
            logger.debug(f"批量更新 hash execution states 失败: {e}")
            pass

    # 2. Handle String Keys (Active Maintenance) (处理 String Key（主动维护）)
    scan_pattern = f"{prefix_key}:*"
    # 如果量大可使用管道更新，但此处为简单和即时一致性采用迭代处理
    
    async for k in r.scan_iter(match=scan_pattern, count=200):
        try:
            key_str = k.decode("utf-8") if isinstance(k, (bytes, bytearray)) else k
            raw = await r.get(key_str)
            if not raw:
                continue
                
            payload_str = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
            payload = json.loads(payload_str)
            
            if not isinstance(payload, dict):
                continue

            # 如果缺失 Symbol 则推断
            if "symbol" not in payload:
                inferred_symbol = _try_infer_symbol_from_key(key_str)
                if inferred_symbol:
                    payload["symbol"] = inferred_symbol
            
            # --- 维护逻辑 ---
            # 1. 老化
            new_payload = age_execution_state(payload, now_ts=now)
            
            # 2. 检查变更
            # 如果 Key 顺序稳定，简单的字符串比较可能就够了，
            # 但 age_execution_state 返回的是副本。
            
            # 比较相关字段以查看逻辑是否更改了内容
            content_changed = (
                new_payload.get("execution_state") != payload.get("execution_state")
            )
            
            if content_changed:
                await r.set(key_str, json.dumps(new_payload, ensure_ascii=False), ex=900)
            else:
                # 优化维护：仅当 TTL 较低（< 5 分钟）或缺失时才 EXPIRE
                current_ttl = await r.ttl(key_str)
                # Redis ttl 返回 -2 表示 Key 不存在，-1 表示无过期，否则返回秒数
                
                # 安全：确保 execution_state 始终具有 TTL，以防止僵尸数据
                if current_ttl == -1:
                    await r.expire(key_str, 900)
                elif current_ttl != -2 and current_ttl < 300:
                    await r.expire(key_str, 900)
                
            execution_states.append(new_payload)
            
        except Exception as e:
            logger.debug(f"维护 execution_state key={key_str} 失败: {e}")
            continue
            
    return execution_states


async def _read_prev_global_overlay(exchange: str, redis_client: Optional[Redis] = None) -> Optional[Dict]:
    r = redis_client or await get_verified_redis_client()
    raw = await r.get(global_key(exchange))
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    try:
        return json.loads(raw) if raw else None
    except Exception:
        return None


async def _store_global_overlay(exchange: str, overlay: Dict, redis_client: Optional[Redis] = None) -> None:
    r = redis_client or await get_verified_redis_client()
    await r.set(global_key(exchange), json.dumps(overlay, ensure_ascii=False))


async def aggregate_and_store_global_overlay(exchange: str, redis_client: Optional[Redis] = None) -> Dict:
    """
    聚合当前交易所下所有持仓的执行状态，并生成/存储全局风控状态。
    这是供外部组件调用的主要接口。
    
    同时会执行“维护”逻辑（TTL续期、冷却检查）。

    NOTE: aggregate_and_store_global_overlay must NOT create new redis clients internally.
    All Redis I/O should use the passed redis_client to ensure connection reuse.
    """
    execution_states = await _read_and_maintain_execution_states(exchange, redis_client=redis_client)
    prev_global = await _read_prev_global_overlay(exchange, redis_client=redis_client)

    account_risk_state = {}  # Placeholder for now
    overlay = aggregate_global_overlay(
        execution_states=execution_states,
        account_risk_state=account_risk_state,
        prev_global_overlay_state=prev_global,
        current_ts=now_ts(),
    )
    await _store_global_overlay(exchange, overlay, redis_client=redis_client)
    return overlay


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exchange", default="binance")
    args = parser.parse_args()

    overlay = await aggregate_and_store_global_overlay(args.exchange)
    print(json.dumps(overlay, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
