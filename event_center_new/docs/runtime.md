# event_center_new 运行时配置

本文冻结 `event_center_new/main.py` 的运行时环境变量契约，避免不同环境口口相传导致配置漂移。

## 0. 版本信息

- `runtime_config_version: event-center-runtime-v1`

### 0.1 变更日志（新到旧）

- version: `event-center-runtime-v1` | date: `2026-03-11` | note: 初始冻结运行时配置，覆盖 loop/stop_on_error/self_check_only/health_key。

维护建议：新增/删除环境变量时，使用 `scripts/bump_event_center_runtime_version.sh` 同步更新版本与变更日志；可先加 `--dry-run` 预览。

## 1. 环境变量总表

| 变量 | 默认值 | 说明 |
|---|---|---|
| `EVENT_CENTER_LAYER_STORE_MODE` | `memory` | 分层写入模式：`memory` / `redis` |
| `EVENT_CENTER_REDIS_URL` | `redis://127.0.0.1:6379/0` | Redis 连接串（仅 `redis` 模式使用） |
| `EVENT_CENTER_STREAM_RAW` | `ec:raw` | raw 层 stream 名称 |
| `EVENT_CENTER_STREAM_NORMALIZED` | `ec:normalized` | normalized 层 stream 名称 |
| `EVENT_CENTER_STREAM_EVIDENCE` | `ec:evidence` | evidence 层 stream 名称 |
| `EVENT_CENTER_STREAM_CONTEXT` | `ec:context` | context 层 stream 名称 |
| `EVENT_CENTER_STREAM_SELECTED` | `ec:selected` | selected 层 stream 名称 |
| `EVENT_CENTER_STREAM_MAXLEN` | `20000` | stream 最大长度（近似裁剪由 `APPROX` 控制） |
| `EVENT_CENTER_STREAM_APPROX` | `true` | Redis `xadd maxlen` 是否采用近似裁剪 |
| `EVENT_CENTER_RUN_LOOP` | `false` | 是否启用循环运行模式 |
| `EVENT_CENTER_RUN_INTERVAL_MS` | `1000` | 循环模式下每轮间隔（毫秒） |
| `EVENT_CENTER_RUN_MAX_TICKS` | `0` | 循环最大轮次；`0` 表示常驻 |
| `EVENT_CENTER_STOP_ON_ERROR` | `false` | 事件处理异常时是否立即退出 |
| `EVENT_CENTER_HEALTH_KEY` | `ec:runner:health` | 健康快照写入 Redis 的 key |
| `EVENT_CENTER_SELF_CHECK_ONLY` | `false` | 启动自检模式：仅初始化+健康上报后退出 |

## 2. 运行模式优先级

`EVENT_CENTER_SELF_CHECK_ONLY=true` 时优先级最高，会直接执行自检并退出，不进入单次运行/循环运行。

在非自检模式下：

- `EVENT_CENTER_RUN_LOOP=true`：进入循环运行
- `EVENT_CENTER_RUN_LOOP=false`：执行单次 `run_once`

## 3. 推荐组合

### 3.1 开发调试（内存模式）

```bash
EVENT_CENTER_LAYER_STORE_MODE=memory \
EVENT_CENTER_RUN_LOOP=false \
python3 -m event_center_new.main
```

### 3.2 CI 快速探活（自检）

```bash
EVENT_CENTER_LAYER_STORE_MODE=redis \
EVENT_CENTER_REDIS_URL=redis://127.0.0.1:6379/0 \
EVENT_CENTER_SELF_CHECK_ONLY=true \
EVENT_CENTER_HEALTH_KEY=ec:runner:health \
python3 -m event_center_new.main
```

### 3.3 准生产常驻（循环）

```bash
EVENT_CENTER_LAYER_STORE_MODE=redis \
EVENT_CENTER_REDIS_URL=redis://127.0.0.1:6379/0 \
EVENT_CENTER_RUN_LOOP=true \
EVENT_CENTER_RUN_INTERVAL_MS=1000 \
EVENT_CENTER_RUN_MAX_TICKS=0 \
EVENT_CENTER_STOP_ON_ERROR=false \
EVENT_CENTER_HEALTH_KEY=ec:runner:health \
python3 -m event_center_new.main
```

### 3.4 严格失败模式（问题定位）

```bash
EVENT_CENTER_RUN_LOOP=true \
EVENT_CENTER_STOP_ON_ERROR=true \
EVENT_CENTER_RUN_MAX_TICKS=1 \
python3 -m event_center_new.main
```

## 4. 健康信号

当启用 `redis` layer store 时，每轮会写入 `EVENT_CENTER_HEALTH_KEY`：

- `heartbeat`
- `last_run_ms`
- `run_count`
- `error_count`
- `last_error`
- `updated_ms`

自检模式写入最小状态：

- `status=ok`
- `self_check_only=true`
- `checked_ms`
- `updated_ms`
