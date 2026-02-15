import asyncio
import logging
import os
import signal
import redis.asyncio as aioredis
from agent_server.config import settings
from agent_server.utils.redis_client import get_verified_redis_client
from agent_server.utils.watchers.exchanges import RedisExchangeWatcher
from agent_server.risk.global_overlay import aggregate_and_store_global_overlay
from agent_server.risk.position_time_semantics import process_positions

logger = logging.getLogger("risk_state_cron")


async def _risk_update_loop(exchange: str, stop_event: asyncio.Event, redis_client: aioredis.Redis):
    """
    特定交易所的全局风控叠加层更新周期任务。
    每 60 秒运行一次。

    NOTE:
    Global overlay updates every 60s.
    Cooldown解除存在 <=60s 延迟，这是有意的稳定性 trade-off。
    """
    logger.info(f"开始交易所的风控更新循环: {exchange}")
    
    last_state_summary = None
    
    while not stop_event.is_set():
        try:
            logger.debug(f"正在更新 {exchange} 的全局叠加层...")
            
            # 更新 Position Time Semantics (每分钟)
            try:
                await process_positions(exchange=exchange, redis_client=redis_client)
            except Exception as e:
                logger.error(f"更新 {exchange} Position Time Semantics 时出错: {e}", exc_info=True)

            # 聚合当前所有仓位的执行状态，生成并存储全局风控状态
            overlay = await aggregate_and_store_global_overlay(exchange, redis_client=redis_client)
            
            # 提取关键状态用于比较变更
            current_regime = overlay.get('global_risk_regime')
            current_cooldown = overlay.get('global_cooldown_state', {}).get('in_cooldown')
            current_summary = (current_regime, current_cooldown)
            
            if current_summary != last_state_summary:
                logger.info(f"[{exchange}] GlobalOverlay changed | Regime: {current_regime} | Cooldown: {current_cooldown}")
                last_state_summary = current_summary
            else:
                logger.debug(f"[{exchange}] GlobalOverlay no change | Regime: {current_regime}")
                
        except Exception as e:
            logger.error(f"更新 {exchange} 全局叠加层时出错: {e}", exc_info=True)

        # 等待 60 秒或直到设置停止事件
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=60.0)
        except asyncio.TimeoutError:
            # 超时意味着 60 秒已过，继续循环
            pass
        except asyncio.CancelledError:
            # 任务被取消
            break

    logger.info(f"已停止交易所的风控更新循环: {exchange}")


async def _run(stop_event: asyncio.Event = None):
    # 使用统一的 Redis 客户端获取方法，确保配置（如 decode_responses）一致
    # ⚠️ 隐含前提：该 redis client 用于多 exchange 并发风控任务
    # 需保证连接池容量 >= exchange_count * 2 (每个循环可能有 read + write)
    redis = await get_verified_redis_client()
    
    # 监听活跃的交易所
    ex_watcher = RedisExchangeWatcher(redis)
    
    if stop_event is None:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()

        def _on_sig(*_):
            logger.info("收到停止信号")
            stop.set()

        loop.add_signal_handler(signal.SIGINT, _on_sig)
        loop.add_signal_handler(signal.SIGTERM, _on_sig)
    else:
        stop = stop_event

    exchange_tasks: dict[str, dict] = {}

    logger.info("风控定时服务已启动。等待交易所...")

    try:
        async for exchanges in ex_watcher.watch_changes():
            cur = set(exchange_tasks.keys())
            
            # 为新交易所启动循环
            for ex in exchanges - cur:
                ex_stop = asyncio.Event()
                task = asyncio.create_task(_risk_update_loop(ex, ex_stop, redis), name=f"risk_cron:{ex}")
                exchange_tasks[ex] = {"task": task, "stop": ex_stop}
                logger.info(f"已注册交易所的风控任务: {ex}")
            
            # 停止已移除交易所的循环
            for ex in cur - exchanges:
                info = exchange_tasks.get(ex)
                if info:
                    info["stop"].set()
                    info["task"].cancel()
                    # 等待任务完成清理
                    await asyncio.gather(info["task"], return_exceptions=True)
                    del exchange_tasks[ex]
                    logger.info(f"已注销交易所的风控任务: {ex}")
            
            if stop.is_set():
                break
            
            # 定期检查交易所变更
            # watch_changes 是一个生成器，当发生变更或定期 yield
            # RedisExchangeWatcher.watch_changes 的实现通常会在内部睡眠或阻塞在 pubsub 上
            # 这里添加一个小的睡眠以防万一，虽然 watch_changes 通常会处理它。
            await asyncio.sleep(0.2)

    except Exception as e:
        logger.error(f"主循环中发生意外错误: {e}", exc_info=True)
    finally:
        logger.info("正在关闭风控定时服务...")
        # 取消所有任务
        for ex, info in list(exchange_tasks.items()):
            info["stop"].set()
            info["task"].cancel()
            await asyncio.gather(info["task"], return_exceptions=True)
        exchange_tasks.clear()
        
        # 关闭资源
        await redis.aclose()
        
        # 如果初始化了，尝试关闭全局 http_client
        # 仅在独立运行时关闭，若由 main 统一调度则由 main 关闭
        if stop_event is None:
            try:
                from agent_server.utils.http_client import http_client
                await http_client.close()
            except ImportError:
                pass
            except Exception as e:
                logger.warning(f"关闭 http_client 时出错: {e}")
            
        logger.info("关闭完成。")


def main():
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
