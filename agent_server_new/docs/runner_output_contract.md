# runner 输出契约（JSON）

更新时间：2026-03-10

适用命令：

```bash
python -m services.agent_server_new.main ... --print-json
```

Schema 文件：

- `agent_server_new/docs/runner_output.schema.json`

## 1. 输出结构

### 1.1 execution 结果可用

```json
{
  "source": "execution",
  "action": "reduce",
  "reason": "position_limit_reached",
  "notes": "..."
}
```

### 1.2 execution 不可用回退 agent

```json
{
  "source": "agent_fallback",
  "action": "add",
  "direction": "long",
  "notes": "..."
}
```

### 1.3 仅 agent 输出

```json
{
  "source": "agent",
  "action": "hold",
  "direction": "none",
  "notes": "..."
}
```

## 2. 退出码语义

- `0`：执行完成（含 execution/agent_fallback/agent）
- `2`：当设置 `--fail-on-execution-reject` 且 execution 返回 `reason` 非空

## 3. 建议

- 自动化脚本优先启用：
  - `--use-execution-result`
  - `--print-json`
  - `--fail-on-execution-reject`

## 4. 解析示例

### 4.1 Shell + jq

```bash
OUT="$(python -m services.agent_server_new.main \
  --exchange binance \
  --symbol ETHUSDT \
  --signal-direction long \
  --use-execution-result \
  --print-json)"

echo "$OUT" | jq -r '.source, .action, .reason // ""'
```

### 4.2 Python

```python
import json
import subprocess

proc = subprocess.run(
    [
        "python",
        "-m",
        "services.agent_server_new.main",
        "--exchange",
        "binance",
        "--symbol",
        "ETHUSDT",
        "--signal-direction",
        "long",
        "--use-execution-result",
        "--print-json",
    ],
    capture_output=True,
    text=True,
    check=False,
)
payload = json.loads(proc.stdout.strip())
print(payload["source"], payload["action"], payload.get("reason"))
```
