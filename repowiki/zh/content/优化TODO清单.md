# 优化TODO清单

## 概述
本文档记录UTaker系统的优化任务，按优先级和依赖关系组织。

## 任务列表

### 1. 交易去重机制 - 防止重复开仓（借鉴NOFX订单同步机制）

**问题描述**
- 当前交易监听服务监听l1事件，当同一币种连续触发l1事件时，可能重复推送交易订单
- 缺少已开仓交易对的记录机制
- 缺少订单ID级别的去重（仅检查交易对不够精确）

**解决方案（借鉴NOFX）**

1. **订单ID去重机制**（核心改进）
   - 不仅检查交易对，还检查订单ID
   - 使用订单ID作为唯一标识，防止同一订单重复推送
   - 订单ID格式：`{symbol}_{timestamp}_{action}_{hash}`

2. **多级去重检查**
   - 第一层：检查订单ID是否已存在（`trading:orders:{exchange}`）
   - 第二层：检查交易对是否已开仓（`trading:open_positions:{exchange}`）
   - 第三层：检查冷却期（已有实现，保持）

3. **订单同步机制**（长期优化）
   - 定期从交易所同步订单历史
   - 检测已成交但未记录的订单
   - 自动清理已平仓的仓位记录

**实现位置**
- `agent_server/trade_listen_main.py` - 在`TradeL1Listener._passes_cooldown`后添加订单ID检查
- `agent_server/agent_workflow/components/executors/trade_decision_execution.py` - 在`_push_to_trade_queue`方法中：
  - 生成订单ID
  - 检查订单ID是否已存在
  - 推送交易时同时记录订单ID和交易对

**Redis Key设计**
- `trading:orders:{exchange}` (Set) - 存储订单ID，用于订单级去重
- `trading:open_positions:{exchange}` (Set) - 存储交易对符号，用于交易对级去重
- `trading:order:{exchange}:{order_id}` (Hash) - 存储订单详情（可选，用于调试）

**代码实现示例**
```python
# 在 trade_decision_execution.py 中
async def _push_to_trade_queue(self, trade_json):
    # 生成订单ID
    symbol = trade_json.get('symbol')
    timestamp = int(time.time() * 1000)
    action = trade_json.get('order_type', 'open')
    order_id = f"{symbol}_{timestamp}_{action}_{hash(str(trade_json))[:8]}"
    
    # 检查订单ID是否已存在
    redis_client = RedisClient()
    if await redis_client.sismember(f"trading:orders:binance", order_id):
        trade_logger.warning(f"订单已存在，跳过: {order_id}")
        return False
    
    # 检查交易对是否已开仓（仅对开仓操作）
    if action == 'open':
        if await redis_client.sismember(f"trading:open_positions:binance", symbol):
            trade_logger.warning(f"交易对已开仓，跳过: {symbol}")
            return False
    
    # 推送交易
    success = await self._push_to_queue(trade_json)
    
    if success:
        # 记录订单ID和交易对
        await redis_client.sadd(f"trading:orders:binance", order_id)
        if action == 'open':
            await redis_client.sadd(f"trading:open_positions:binance", symbol)
    
    return success
```

**状态**: 待实现

---

### 2. 仓位跟踪与自动清理（借鉴NOFX PositionBuilder）

**问题描述**
- 需要实时监控仓位状态，当仓位成交完成（平仓）时，自动从Redis交易集合中移除
- 需要统一处理开仓/平仓逻辑，支持仓位合并和部分平仓
- 需要自动计算已实现盈亏

**解决方案（借鉴NOFX PositionBuilder）**

1. **实现PositionBuilder类**（核心改进）
   - 统一处理开仓/平仓逻辑
   - 支持仓位合并（加权平均入场价）
   - 支持部分平仓
   - 自动计算已实现盈亏

2. **仓位快照机制**
   - 定期从交易所获取真实仓位
   - 对比Redis记录的仓位
   - 自动清理已平仓的仓位记录

3. **仓位变化监听**
   - 监听WebSocket仓位变化事件
   - 当仓位数量变为0时，自动清理Redis记录

**实现位置**
- 新建：`agent_server/utils/position_builder.py` - PositionBuilder类
- `data_server/binance/ws_binance/user_ws.py` - 集成PositionBuilder和仓位快照
- `data_server/binance/ws_binance/utils/binance_pos_analysis.py` - 仓位分析逻辑

**代码实现示例**
```python
# 新建：agent_server/utils/position_builder.py
class PositionBuilder:
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def process_trade(self, trade_data):
        """处理交易，自动更新仓位"""
        action = trade_data.get('order_type')
        symbol = trade_data.get('symbol')
        
        if action == 'open':
            await self._handle_open(trade_data)
        elif action == 'close':
            await self._handle_close(trade_data)
    
    async def _handle_open(self, trade_data):
        """开仓：创建新仓位或合并到现有仓位"""
        symbol = trade_data['symbol']
        side = trade_data.get('position_side', 'LONG')
        
        # 检查是否已有仓位
        position_key = f"position:binance:{symbol}:{side}"
        existing = await self.redis.hgetall(position_key)
        
        if existing:
            # 合并仓位，计算加权平均入场价
            old_qty = float(existing.get('quantity', 0))
            old_price = float(existing.get('entry_price', 0))
            new_qty = float(trade_data.get('quantity', 0))
            new_price = float(trade_data.get('openAvgPx', 0))
            
            total_qty = old_qty + new_qty
            avg_price = (old_price * old_qty + new_price * new_qty) / total_qty
            
            await self.redis.hset(position_key, {
                'quantity': total_qty,
                'entry_price': avg_price,
                'updated_at': int(time.time() * 1000)
            })
        else:
            # 创建新仓位
            await self.redis.hset(position_key, {
                'symbol': symbol,
                'side': side,
                'quantity': trade_data.get('quantity', 0),
                'entry_price': trade_data.get('openAvgPx', 0),
                'created_at': int(time.time() * 1000),
                'updated_at': int(time.time() * 1000)
            })
            # 添加到开仓集合
            await self.redis.sadd(f"trading:open_positions:binance", symbol)
    
    async def _handle_close(self, trade_data):
        """平仓：部分平仓或完全平仓"""
        symbol = trade_data['symbol']
        side = trade_data.get('position_side', 'LONG')
        close_qty = float(trade_data.get('quantity', 0))
        
        position_key = f"position:binance:{symbol}:{side}"
        position = await self.redis.hgetall(position_key)
        
        if not position:
            return
        
        position_qty = float(position.get('quantity', 0))
        
        if close_qty < position_qty:
            # 部分平仓
            new_qty = position_qty - close_qty
            await self.redis.hset(position_key, {
                'quantity': new_qty,
                'updated_at': int(time.time() * 1000)
            })
        else:
            # 完全平仓
            await self.redis.delete(position_key)
            # 从开仓集合中移除
            await self.redis.srem(f"trading:open_positions:binance", symbol)
```

**仓位快照实现**
```python
# 在 user_ws.py 中
async def create_position_snapshot(self):
    """定期创建仓位快照，确保与交易所一致"""
    # 1. 从交易所获取真实仓位
    real_positions = await self.get_positions()
    real_symbols = {p['symbol'] for p in real_positions if float(p.get('positionAmt', 0)) != 0}
    
    # 2. 从Redis获取记录的仓位
    recorded_symbols = await self.redis.smembers("trading:open_positions:binance")
    
    # 3. 对比差异，清理已平仓的仓位
    for symbol in recorded_symbols:
        if symbol not in real_symbols:
            await self.redis.srem("trading:open_positions:binance", symbol)
            trade_logger.info(f"仓位已平仓，清理记录: {symbol}")
    
    # 4. 更新Redis集合
    for symbol in real_symbols:
        await self.redis.sadd("trading:open_positions:binance", symbol)
```

**触发条件**
- 仓位数量变为0
- 仓位被完全平仓
- 检测到仓位移除事件
- 定期快照检测（每5分钟）

**状态**: 待实现（依赖任务1）

---

### 3. 仓位风控Agent（借鉴NOFX双层风控系统）

**问题描述**
- 需要对已开仓位进行实时风控监控
- 定期检查仓位风险，执行止损、止盈等风控操作
- 需要在开仓前进行代码级风控检查（硬性限制）

**解决方案（借鉴NOFX双层风控）**

1. **代码级风控（CODE ENFORCED）**（核心改进）
   - 最大仓位数量限制
   - 单仓位价值比例限制（BTC/ETH vs Altcoin不同）
   - 最小仓位大小限制
   - 最大保证金使用率限制
   - 在开仓前强制执行，不依赖AI

2. **策略级风控（AI GUIDED）**
   - 最小风险回报比（3:1）
   - 最小置信度要求
   - 动态止损止盈

3. **实时仓位监控**
   - 定期检查已开仓位的风险
   - 执行止损、止盈等风控操作

**实现位置**
- 新建：`agent_server/utils/risk_control.py` - RiskController类（代码级风控）
- `agent_server/agent_workflow/components/executors/trade_decision_execution.py` - 集成风控检查
- `data_server/binance/ws_binance/user_ws.py` - 添加定时任务（实时监控）
- `agent_server/agents/experts/analysis/position_risk.py` - 风控专家（策略级风控）

**代码实现示例**
```python
# 新建：agent_server/utils/risk_control.py
class RiskController:
    def __init__(self, config=None):
        config = config or {}
        self.max_positions = config.get('max_positions', 3)
        self.btc_eth_max_ratio = config.get('btc_eth_max_position_ratio', 5.0)
        self.altcoin_max_ratio = config.get('altcoin_max_position_ratio', 1.0)
        self.min_position_size = config.get('min_position_size', 12.0)
        self.max_margin_usage = config.get('max_margin_usage', 0.9)
        self.min_risk_reward_ratio = config.get('min_risk_reward_ratio', 3.0)
    
    def _is_btc_eth(self, symbol):
        """判断是否为BTC或ETH"""
        return symbol in ['BTCUSDT', 'ETHUSDT']
    
    async def check_open_position(self, symbol, position_size_usd, equity, current_positions, tp_price, sl_price, entry_price):
        """检查是否可以开仓（代码级风控）"""
        # 1. 检查最大仓位数量
        if len(current_positions) >= self.max_positions:
            return False, f"已达到最大仓位数量: {len(current_positions)}/{self.max_positions}"
        
        # 2. 检查单仓位价值比例
        if self._is_btc_eth(symbol):
            max_value = equity * self.btc_eth_max_ratio
        else:
            max_value = equity * self.altcoin_max_ratio
        
        if position_size_usd > max_value:
            return False, f"仓位价值超过限制: {position_size_usd:.2f} > {max_value:.2f} (比例: {self.btc_eth_max_ratio if self._is_btc_eth(symbol) else self.altcoin_max_ratio}x)"
        
        # 3. 检查最小仓位大小
        if position_size_usd < self.min_position_size:
            return False, f"仓位大小低于最小值: {position_size_usd:.2f} < {self.min_position_size:.2f}"
        
        # 4. 检查保证金使用率
        total_margin = sum(p.get('margin', 0) for p in current_positions) + position_size_usd
        margin_usage = total_margin / equity if equity > 0 else 0
        if margin_usage > self.max_margin_usage:
            return False, f"保证金使用率超过限制: {margin_usage:.2%} > {self.max_margin_usage:.2%}"
        
        # 5. 检查风险回报比
        if entry_price > 0 and tp_price > 0 and sl_price > 0:
            if symbol.startswith('LONG') or 'LONG' in str(symbol):
                risk = abs(entry_price - sl_price)
                reward = abs(tp_price - entry_price)
            else:
                risk = abs(sl_price - entry_price)
                reward = abs(entry_price - tp_price)
            
            if risk > 0:
                risk_reward_ratio = reward / risk
                if risk_reward_ratio < self.min_risk_reward_ratio:
                    return False, f"风险回报比过低: {risk_reward_ratio:.2f}:1 < {self.min_risk_reward_ratio:.2f}:1"
        
        return True, "通过"
```

**集成到交易决策流程**
```python
# 在 trade_decision_execution.py 中
from agent_server.utils.risk_control import RiskController

# 在 execute 方法中，推送交易前检查
risk_controller = RiskController()
can_open, reason = await risk_controller.check_open_position(
    symbol=symbol,
    position_size_usd=position_size_usd,
    equity=equity,
    current_positions=current_positions,
    tp_price=tp_price,
    sl_price=sl_price,
    entry_price=mark_price
)

if not can_open:
    trade_logger.warning(f"风控拦截: {symbol} - {reason}")
    td_output['should_execute'] = False
    td_output['risk_reject_reason'] = reason
    return self._safe_json_dumps(td_output)
```

**监控周期**
- 代码级风控：开仓前立即检查
- 实时监控：30秒-60秒一次
- 可根据市场波动性动态调整

**状态**: 待实现（依赖任务2）

---

### 4. L0到L1逻辑梳理与关键信号改造

**问题描述**
- 需要整理当前L0到L1的事件处理逻辑
- 考虑改造关键信号产生机制，支持自定义关键信号监听

**当前逻辑梳理**

**L0处理器（l0_processor.py）**
- 输入：`raw_events` Stream
- 处理：时间窗口聚合、信号一致性验证、方向确认
- 输出：`l0_events` Stream
- 关键参数：
  - `window_seconds`: 300秒（5分钟窗口）
  - `window_count`: 5个事件
  - `min_score`: 2.0（最小强度）
  - `consistency_ratio`: 0.6（一致性比率）

**L1聚合器（l1_aggregator.py）**
- 输入：`l0_events` Stream
- 处理：跨时间框架分桶聚合、市场状态判定、方向汇总
- 输出：`l1_events` Stream
- 关键逻辑：
  - 按时间框架分桶（short/mid/long）
  - 计算市场状态（trend/range/neutral）
  - 汇总总分和方向

**改造方案**
- 创建新的关键信号生成器
- 支持自定义信号规则配置
- 添加新的监听Agent专门处理关键信号
- 关键信号可绕过常规L0/L1流程，直接触发交易决策

**实现位置**
- 新建：`event_center/pipeline/critical_signal_generator.py` - 关键信号生成器
- 新建：`agent_server/critical_signal_listener.py` - 关键信号监听器
- 配置文件：`event_center/configs/critical_signals.yml` - 关键信号规则

**状态**: 待分析设计

---

### 5. 价格延迟问题优化（借鉴NOFX多级缓存机制）

**问题描述**
- 当前价格获取存在延迟，影响交易决策的实时性
- 价格数据可能过期，导致交易决策不准确

**问题分析**
- 价格数据来源：`price:binance:{symbol}` (Redis Hash)
- 更新频率：通过WebSocket `aggTrade`事件更新
- 可能延迟原因：
  - WebSocket消息处理延迟
  - Redis写入延迟
  - 价格读取时使用旧数据
  - 缺少数据新鲜度检测

**优化方案（借鉴NOFX）**

1. **实现价格缓存类**（核心改进）
   - 在内存中维护最新价格缓存
   - 减少Redis读取次数
   - 支持TTL（时间生存期）检查

2. **数据新鲜度检测**
   - 读取价格时检查时间戳
   - 如果价格数据超过阈值（如5秒），标记为过期
   - 跳过过期数据，避免使用旧价格

3. **多级价格获取策略**
   - 第一优先级：内存缓存（最快）
   - 第二优先级：Redis（次快）
   - 第三优先级：WebSocket实时流（最慢但最新）

4. **在WebSocket中更新缓存**
   - 处理`aggTrade`事件时，同时更新内存缓存和Redis
   - 确保缓存和Redis数据一致

**实现位置**
- 新建：`agent_server/utils/realtime_price_cache.py` - PriceCache类
- `agent_server/tools/price_fetcher.py` - 集成PriceCache
- `data_server/binance/ws_binance/market_ws.py` - 在`on_agg_trade`中更新缓存
- `agent_server/agent_workflow/components/executors/trade_decision_execution.py` - 使用PriceCache获取价格

**代码实现示例**
```python
# 新建：agent_server/utils/realtime_price_cache.py
from collections import defaultdict
import time

class PriceCache:
    """实时价格缓存（借鉴NOFX）"""
    def __init__(self, ttl=5.0):
        self.cache = defaultdict(dict)
        self.ttl = ttl  # 5秒TTL
    
    def get_price(self, exchange, symbol):
        """获取价格，如果过期返回None"""
        if symbol in self.cache[exchange]:
            price_data = self.cache[exchange][symbol]
            if time.time() - price_data['timestamp'] < self.ttl:
                return price_data['price']
            else:
                # 过期，删除
                del self.cache[exchange][symbol]
        return None
    
    def set_price(self, exchange, symbol, price):
        """更新价格"""
        self.cache[exchange][symbol] = {
            'price': price,
            'timestamp': time.time()
        }
    
    def is_stale(self, exchange, symbol):
        """检查价格是否过期"""
        if symbol not in self.cache[exchange]:
            return True
        return time.time() - self.cache[exchange][symbol]['timestamp'] > self.ttl
    
    def clear(self, exchange=None, symbol=None):
        """清理缓存"""
        if exchange and symbol:
            if symbol in self.cache[exchange]:
                del self.cache[exchange][symbol]
        elif exchange:
            self.cache[exchange].clear()
        else:
            self.cache.clear()

# 全局实例
_price_cache = PriceCache()

def get_price_cache():
    """获取全局价格缓存实例"""
    return _price_cache
```

**在WebSocket中更新缓存**
```python
# 在 market_ws.py 中
from agent_server.utils.realtime_price_cache import get_price_cache

price_cache = get_price_cache()

async def on_agg_trade(self, data):
    """处理聚合交易事件，更新价格缓存"""
    symbol = data['s']
    price = float(data['p'])
    
    # 更新内存缓存
    price_cache.set_price('binance', symbol, price)
    
    # 同时更新Redis
    await redis.hset(f"price:binance:{symbol}", {
        "price": price,
        "timestamp": int(time.time() * 1000)
    })
```

**在交易决策时使用缓存**
```python
# 在 trade_decision_execution.py 中
from agent_server.utils.realtime_price_cache import get_price_cache

price_cache = get_price_cache()

async def _get_mark_price(self, exchange, symbol):
    """获取标记价格（优先使用缓存）"""
    # 第一优先级：内存缓存
    price = price_cache.get_price(exchange, symbol)
    if price is not None:
        return price
    
    # 第二优先级：Redis
    redis_client = RedisClient()
    price_data = await redis_client.hgetall(f"price:{exchange}:{symbol}")
    if price_data:
        price = float(price_data.get('price', 0))
        timestamp = int(price_data.get('timestamp', 0))
        
        # 检查是否过期（5秒）
        if time.time() * 1000 - timestamp > 5000:
            trade_logger.warning(f"价格数据过期: {symbol} (延迟: {time.time() * 1000 - timestamp}ms)")
            return None
        
        # 更新缓存
        price_cache.set_price(exchange, symbol, price)
        return price
    
    # 第三优先级：从API获取（如果可用）
    return None
```

**状态**: 待实现

---

### 6. 开仓点计算优化 - 大周期K线范围（借鉴NOFX多时间框架验证）

**问题描述**
- 当前开仓点计算使用最近20根K线，不够合理
- 应该基于大周期K线的上下范围来确定开仓点
- 缺少多时间框架验证机制

**当前实现**
- 位置：`agent_server/configs/prompts/core_philosophy.py`
- 逻辑：检查最近20根K线的最高点和最低点
- 问题：20根K线范围太小，容易在极值位置开仓

**优化方案（借鉴NOFX多时间框架分析）**

1. **使用大周期K线**（核心改进）
   - 使用15m或30m周期的K线数据
   - 计算大周期K线的支撑/阻力范围
   - 至少使用48根K线（12-24小时数据）

2. **范围计算**
   - 计算大周期K线的最高点和最低点（建议使用48-100根K线）
   - 计算价格区间：`max_high - min_low`
   - 计算当前价格在区间中的位置：`(current_price - min_low) / price_range`
   - 根据趋势强度动态调整验证范围

3. **开仓点验证逻辑**
   - 做多验证：检查是否在价格区间上15%-20%范围内（避免在最高点开仓）
   - 做空验证：检查是否在价格区间下15%-20%范围内（避免在最低点开仓）
   - Strong趋势：可放宽到区间上5%以内
   - Moderate趋势：1%以内或区间15%范围
   - Weak/Neutral趋势：2%以内或区间20%范围

4. **风险回报比验证**（借鉴NOFX）
   - 强制要求最小风险回报比（3:1）
   - 验证止损止盈价格合理性

**实现位置**
- `agent_server/agent_workflow/components/executors/trade_decision_execution.py` - 添加`validate_entry_point`方法
- `agent_server/configs/prompts/core_philosophy.py` - 更新交易哲学提示词（可选，主要逻辑在代码中）

**代码实现示例**
```python
# 在 trade_decision_execution.py 中
async def _validate_entry_point(self, symbol, action, current_price, klines_15m, trend_strength=None):
    """验证开仓点是否合理（借鉴NOFX）"""
    if len(klines_15m) < 48:
        return False, "K线数据不足（需要至少48根15m K线）"
    
    # 计算大周期范围（最近48根K线）
    recent_klines = klines_15m[-48:]
    highs = [float(k.get('h', 0)) for k in recent_klines]
    lows = [float(k.get('l', 0)) for k in recent_klines]
    
    max_high = max(highs)
    min_low = min(lows)
    price_range = max_high - min_low
    
    if price_range <= 0:
        return False, "价格区间无效"
    
    # 计算当前价格在区间中的位置（0-1）
    price_position = (current_price - min_low) / price_range
    
    # 做多验证：避免在最高点开仓
    if action == 'OPEN_LONG':
        # 根据趋势强度调整阈值
        if trend_strength == 'strong':
            threshold = 0.95  # Strong趋势：允许在区间上5%开仓
        elif trend_strength == 'moderate':
            threshold = 0.85  # Moderate趋势：禁止在区间上15%开仓
        else:
            threshold = 0.80  # Weak/Neutral趋势：禁止在区间上20%开仓
        
        if price_position > threshold:
            return False, f"价格在区间高位: {price_position:.2%} > {threshold:.2%}，禁止做多"
    
    # 做空验证：避免在最低点开仓
    elif action == 'OPEN_SHORT':
        # 根据趋势强度调整阈值
        if trend_strength == 'strong':
            threshold = 0.05  # Strong趋势：允许在区间下5%开仓
        elif trend_strength == 'moderate':
            threshold = 0.15  # Moderate趋势：禁止在区间下15%开仓
        else:
            threshold = 0.20  # Weak/Neutral趋势：禁止在区间下20%开仓
        
        if price_position < threshold:
            return False, f"价格在区间低位: {price_position:.2%} < {threshold:.2%}，禁止做空"
    
    return True, f"开仓点合理（位置: {price_position:.2%}）"

async def _validate_risk_reward_ratio(self, entry_price, tp_price, sl_price, action):
    """验证风险回报比（借鉴NOFX，最小3:1）"""
    if entry_price <= 0 or tp_price <= 0 or sl_price <= 0:
        return False, "价格无效"
    
    if action == 'OPEN_LONG':
        risk = abs(entry_price - sl_price)
        reward = abs(tp_price - entry_price)
    else:  # OPEN_SHORT
        risk = abs(sl_price - entry_price)
        reward = abs(entry_price - tp_price)
    
    if risk <= 0:
        return False, "风险为0，无法计算风险回报比"
    
    risk_reward_ratio = reward / risk
    min_ratio = 3.0
    
    if risk_reward_ratio < min_ratio:
        return False, f"风险回报比过低: {risk_reward_ratio:.2f}:1 < {min_ratio:.2f}:1"
    
    return True, f"风险回报比: {risk_reward_ratio:.2f}:1"

# 在 execute 方法中使用
async def execute(self, ctx: StepInput):
    # ... 现有代码 ...
    
    # 获取15m K线数据
    klines_15m = await self._get_klines(symbol, '15m', 100)
    
    # 验证开仓点（仅对开仓操作）
    if decision in ['OPEN_LONG', 'OPEN_SHORT']:
        trend_strength = query.get('trend_analysis', {}).get('strength', 'weak')
        is_valid, reason = await self._validate_entry_point(
            symbol, decision, mark_price, klines_15m, trend_strength
        )
        if not is_valid:
            trade_logger.warning(f"开仓点验证失败: {symbol} - {reason}")
            td_output['should_execute'] = False
            td_output['entry_point_reject_reason'] = reason
            return self._safe_json_dumps(td_output)
        
        # 验证风险回报比
        if tp_trigger_px > 0 and sl_trigger_px > 0:
            is_valid, reason = await self._validate_risk_reward_ratio(
                mark_price, tp_trigger_px, sl_trigger_px, decision
            )
            if not is_valid:
                trade_logger.warning(f"风险回报比验证失败: {symbol} - {reason}")
                td_output['should_execute'] = False
                td_output['risk_reward_reject_reason'] = reason
                return self._safe_json_dumps(td_output)
```

**K线数据要求**
- 15m周期：至少48根（12小时）
- 30m周期：至少48根（24小时）
- 优先使用15m，数据不足时使用30m
- 如果数据不足，拒绝开仓

**状态**: 待实现

---

## 实施优先级（已根据NOFX借鉴建议优化）

### 高优先级（核心功能，借鉴NOFX）
1. **任务1** - 交易去重机制（借鉴NOFX订单同步机制）
   - 订单ID去重（核心改进）
   - 多级去重检查
   - 防止重复开仓

2. **任务5** - 价格延迟优化（借鉴NOFX多级缓存）
   - 实现PriceCache类
   - 数据新鲜度检测
   - 多级价格获取策略

3. **任务2** - 仓位跟踪与自动清理（借鉴NOFX PositionBuilder）
   - 实现PositionBuilder类
   - 仓位快照机制
   - 自动清理已平仓仓位

### 中优先级（风控与稳定性，借鉴NOFX）
4. **任务3** - 仓位风控Agent（借鉴NOFX双层风控系统）
   - 代码级风控（硬性限制）
   - 策略级风控（AI指导）
   - 实时仓位监控

5. **任务6** - 开仓点计算优化（借鉴NOFX多时间框架验证）
   - 大周期K线范围计算
   - 开仓点验证逻辑
   - 风险回报比验证

### 低优先级（功能增强）
6. **任务4** - L0/L1逻辑梳理与改造（长期优化）
   - 关键信号生成器
   - 自定义信号规则

## 依赖关系（已更新）

```
任务1 (交易去重) - 独立，可优先实现
  └─> 任务2 (仓位跟踪) - 依赖任务1

任务5 (价格优化) - 独立，可优先实现

任务2 (仓位跟踪)
  └─> 任务3 (风控Agent) - 依赖任务2

任务6 (开仓点优化) - 独立，可并行实现

任务4 (信号改造) - 独立，长期优化
```

**推荐实施顺序**：
1. 任务1 + 任务5（可并行，都是独立任务）
2. 任务2（依赖任务1）
3. 任务3（依赖任务2）
4. 任务6（独立，可并行）
5. 任务4（长期优化）

## 注意事项（已根据NOFX借鉴建议更新）

1. **Redis Key命名规范**
   - 使用统一前缀：`trading:`
   - 集合类型使用Set，便于快速查询
   - 订单ID格式：`{symbol}_{timestamp}_{action}_{hash}`

2. **错误处理**
   - 所有Redis操作需要异常处理
   - 网络异常时不应阻塞主流程
   - 价格缓存失败时fallback到Redis

3. **日志记录**
   - 记录所有开仓/平仓操作
   - 记录风控决策过程
   - 记录价格缓存命中/未命中情况
   - 记录开仓点验证结果

4. **测试建议**
   - 使用模拟盘测试所有功能
   - 验证并发场景下的去重机制
   - 验证仓位变化检测的准确性
   - 验证价格缓存的数据新鲜度
   - 验证开仓点验证逻辑的准确性

5. **性能优化**
   - 价格缓存使用内存，减少Redis读取
   - 订单去重使用Set，O(1)查询复杂度
   - 仓位快照定期执行，避免频繁查询

6. **数据一致性**
   - 确保订单ID和交易对记录同步
   - 确保仓位快照与交易所一致
   - 确保价格缓存与Redis一致

## 相关文件

- `agent_server/trade_listen_main.py` - 交易监听主服务
- `agent_server/trade_decision_main.py` - 交易决策入口
- `agent_server/agent_workflow/components/executors/trade_decision_execution.py` - 交易决策执行
- `data_server/binance/ws_binance/user_ws.py` - 仓位跟踪服务
- `data_server/binance/ws_binance/utils/binance_pos_analysis.py` - 仓位分析
- `event_center/pipeline/l0_processor.py` - L0处理器
- `event_center/pipeline/l1_aggregator.py` - L1聚合器
- `agent_server/tools/price_fetcher.py` - 价格获取工具
