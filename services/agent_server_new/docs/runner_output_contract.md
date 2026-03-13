# runner 输出契约（JSON）

更新时间：2026-03-13

语义说明：`ExecutionPlan` 属于 agent 语义输出，不等价于 execution 最终动作；最终风控与动作以 execution 返回为准。

适用命令：

```bash
python -m services.agent_server_new.main ... --print-json
```

Schema 文件：

- `services/agent_server_new/docs/runner_output.schema.json`
- `services/agent_server_new/docs/decision_trace.schema.json`（DecisionTrace 记录契约）
- `services/agent_server_new/docs/llm_signal_decision.schema.json`（LLM 信号判定输出契约）

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

## 5. DecisionTrace 契约（recorder 输出）

当 workflow 配置了 recorder，会写出 `agent_name="decision_trace"` 的结构化记录。

关键字段：
- `event_id/exchange/symbol/ts`
- `signal_verdict/execution_plan`
- `routing`（`pipeline_mode/decision_agent_key/decision_mode/llm_parse_status/llm_contract_error_code/llm_contract_errors/router_config_source/router_config_version/prompt_config_source/prompt_config_version/event_type_raw/event_type_normalized/event_type_match_mode`）
  - `pipeline_mode` 固定为 `minimal`
  - `llm_contract_error_code`：`""|llm_raw_content_missing|llm_json_parse_error|llm_json_not_object|llm_schema_validation_failed|llm_confidence_parse_error`
  - `llm_contract_errors`：字符串数组，最多 8 条
- `llm_observation`（固定语义：`status/provider/model/raw_content_hash`）

语义边界：
- `decision_trace` 已移除 `intent/rule_plan/strategy_gate_result/risk_gate` 历史语义快照字段，避免与 execution 权责混淆。
- `execution_plan.sizing` 与 `execution_plan.allowance` 为 agent 语义建议字段，execution 可按自身规则覆盖或忽略。
- 最终风控阻断与执行动作以 `execution_service` 返回结果为唯一权威。

对应 schema：
- `services/agent_server_new/docs/decision_trace.schema.json`
