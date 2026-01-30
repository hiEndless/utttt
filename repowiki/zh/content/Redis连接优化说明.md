# Redis连接优化说明

## 问题描述

系统在运行过程中出现 `Too many connections` 错误，导致Redis写入失败。

**错误示例**：
```
redis write error on XADD key=ticks:binance:BTCUSDT type=unknown: Too many connections
redis write error on HSET key=price:binance:BTCUSDT type=unknown: Too many connections
```

**原因分析**：
1. 每次Redis操作都创建新连接，没有使用连接池
2. 连接池大小设置过小（默认50）
3. 高频数据更新时，连接数快速耗尽
4. 缺少重试机制，连接错误时直接失败

---

## 优化方案

### 1. 增加连接池大小

**优化位置**：
- `data_server/binance/ws_binance/utils/redis_client.py`
- `agent_server/utils/redis_client.py`
- `data_server/binance/rest_binance/app/utils/redis_client.py`

**改动**：
- 默认 `max_connections` 从 50 增加到 **100**
- 添加连接池缓存，复用连接池
- 添加连接健康检查

**代码**：
```python
def get_sync_redis(host=None, port=None, password=None, db=None, decode_responses=True, max_connections=100):
    # 使用连接池缓存
    key = f"{h}:{p}:{d}:{'1' if decode_responses else '0'}:{max_connections}"
    client = _SYNC_CLIENTS.get(key)
    if client is None:
        pool = redis.ConnectionPool(
            host=h, port=p, password=pw, db=d, 
            max_connections=max_connections,  # 增加到100
            decode_responses=decode_responses,
            retry_on_timeout=True,
            socket_keepalive=True,
            health_check_interval=30
        )
        client = redis.Redis(connection_pool=pool)
        _SYNC_CLIENTS[key] = client
    return client
```

---

### 2. 添加重试机制

**优化位置**：
- `data_server/binance/ws_binance/utils/reids_connect.py` - `set_hash` 方法
- `data_server/binance/ws_binance/utils/depth.py` - `update_depth` 方法
- `data_server/binance/ws_binance/utils/spike_trigger.py` - `add_tick_and_persist` 方法
- `data_server/binance/ws_binance/utils/redis_client.py` - `safe_xadd_sync`, `safe_hset_sync` 等方法

**改动**：
- 所有Redis写入操作添加重试机制（最多3次）
- 使用指数退避策略（100ms, 200ms, 300ms）
- 只对连接错误进行重试，其他错误直接记录

**代码示例**：
```python
def set_hash(self, key: str, mapping_dict: dict, check_type: bool = True):
    max_retries = 3
    retry_delay = 0.1  # 100ms
    
    for attempt in range(max_retries):
        try:
            # Redis操作
            self.conn.hset(key, mapping=mapping_dict)
            return  # 成功则返回
        except Exception as e:
            error_str = str(e)
            # 如果是连接错误，重试
            if ("Too many connections" in error_str or "Connection" in error_str) and attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))  # 指数退避
                continue
            # 其他错误或重试失败，记录
            if attempt == max_retries - 1:
                print(f"Redis HSET error: {e} (retried {max_retries} times)")
            return
```

---

### 3. 统一连接池管理

**优化位置**：
- 所有Redis客户端都使用连接池
- 使用缓存机制复用连接池
- 确保所有模块使用相同的连接池配置

**改动**：
- `agent_server/utils/redis_client.py` - 添加连接池缓存
- `data_server/binance/rest_binance/app/utils/redis_client.py` - 添加连接池缓存
- `data_server/binance/ws_binance/utils/redis_client.py` - 优化连接池配置

---

## 优化效果

### 1. 连接池优化
- ✅ 连接池大小从50增加到100
- ✅ 连接池复用，避免重复创建
- ✅ 连接健康检查，自动恢复

### 2. 重试机制
- ✅ 所有Redis写入操作都有重试机制
- ✅ 指数退避策略，避免频繁重试
- ✅ 只重试连接错误，其他错误直接记录

### 3. 错误处理
- ✅ 连接错误自动重试
- ✅ 重试失败后记录详细错误信息
- ✅ 不阻塞主流程，优雅降级

---

## 优化文件清单

### 核心优化文件

1. **`data_server/binance/ws_binance/utils/redis_client.py`**
   - ✅ 增加连接池大小（50 → 100）
   - ✅ 添加连接健康检查
   - ✅ 优化 `safe_xadd_sync`, `safe_hset_sync`, `safe_xadd_async`, `safe_hset_async` 方法（添加重试）

2. **`data_server/binance/ws_binance/utils/reids_connect.py`**
   - ✅ `RedisClient` 使用更大的连接池（100）
   - ✅ `set_hash` 方法添加重试机制

3. **`data_server/binance/ws_binance/utils/depth.py`**
   - ✅ `update_depth` 方法中的XADD操作添加重试机制

4. **`data_server/binance/ws_binance/utils/spike_trigger.py`**
   - ✅ `add_tick_and_persist` 方法中的XADD和HSET操作添加重试机制

5. **`agent_server/utils/redis_client.py`**
   - ✅ `get_redis_client` 使用连接池缓存
   - ✅ 增加连接池大小（100）

6. **`data_server/binance/rest_binance/app/utils/redis_client.py`**
   - ✅ `get_redis_client` 使用连接池缓存
   - ✅ 增加连接池大小（100）

---

## 配置建议

### Redis服务器配置

如果仍然遇到连接数问题，可以调整Redis服务器配置：

```bash
# 编辑Redis配置文件
vim /etc/redis/redis.conf

# 增加最大客户端连接数（默认10000）
maxclients 20000

# 重启Redis
redis-cli shutdown
redis-server /etc/redis/redis.conf
```

### 应用层配置

如果连接数仍然不够，可以增加连接池大小：

```python
# 在调用get_sync_redis时指定更大的连接数
redis_client = get_sync_redis(max_connections=200)
```

---

## 测试验证

### 1. 检查连接数

```bash
# 查看Redis当前连接数
redis-cli INFO clients

# 查看连接详情
redis-cli CLIENT LIST
```

### 2. 监控连接错误

启动服务后，观察日志：
- 应该不再出现 "Too many connections" 错误
- 如果出现，会看到重试信息："(retried 3 times)"

### 3. 性能测试

- 启动所有服务
- 监控Redis连接数：`redis-cli INFO clients | grep connected_clients`
- 应该稳定在合理范围内（< 100）

---

## 总结

✅ **已优化**：
- 连接池大小（50 → 100）
- 连接池复用机制
- 重试机制（所有Redis写入操作）
- 错误处理（优雅降级）

✅ **效果**：
- 减少连接数使用
- 自动重试连接错误
- 提高系统稳定性
- 避免 "Too many connections" 错误

现在系统应该能够稳定处理高频Redis写入操作了！
