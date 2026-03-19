# 3月7日交易决策日志分析：为何「可以开单的单子没有开仓」

## 一、日志结论概览

- **trade_decision_20260307.log**：当日所有决策均为 **NO_ACTION**，无一次 OPEN_LONG/OPEN_SHORT 且 pushed=True。
- **trade_ai_reasoning_20260307.log**：所有推理结果均为 `should_execute: false`，理由集中在以下几类。

## 二、NO_ACTION 的主要原因分类

| 原因 | 典型标的 | 说明 |
|------|----------|------|
| **execution_constraint.forbidden_actions 包含 'open'** | TAKEUSDT, VVVUSDT, ETHUSDT | 上游（SignalValidation → ExecutionBoundary）已禁止开仓，本 Agent 必须服从 |
| **audit_confidence.structural_clarity == DOMINANT_CONFLICT** | 同上 | 与上一条同源：structural_clarity 为 DOMINANT_CONFLICT 时，ExecutionBoundary 会把 "open" 加入 forbidden_actions |
| **短期结构拥挤 risk 高（规则 8）** | POWERUSDT, PLAYUSDT, BTCUSDT, ETHUSDT | short_term.crowding_risk == "high" 且 dominant_cycle 为 mid_term、方向对齐 → 当前提示词要求 NO_ACTION |
| **长期结构否决** | BTCUSDT | long_term.leverage_extreme == true 且 crowding_percentile.zone == "elevated" |
| **l1_total_score 过低** | PLAYUSDT | 绝对值 < 5 或 < 10 |

## 三、问题出在「提示词」还是「上游」？

### 1. 上游已禁止开仓（本 Agent 无法放开）

- **forbidden_actions 包含 "open"** 来自 `ExecutionBoundary`：当 `signal_validation.audit_confidence.structural_clarity == "DOMINANT_CONFLICT"` 时，会往 `forbidden_actions` 里加入 `"open"`。
- 因此，只要 **SignalValidation** 输出 `structural_clarity = DOMINANT_CONFLICT`（例如短周期与主导周期方向冲突、或结构冲突），本 Agent 的提示词已规定「绝不能输出 OPEN_*」，**无法通过改提示词覆盖**。
- 若你观察到「很多本该能开的单」被这类理由拦住，需要检查：
  - **SignalValidation** 在什么条件下输出 DOMINANT_CONFLICT（是否在「仅短期拥挤、中期对齐」时也标成 CONFLICT）；
  - 是否要在 **ExecutionBoundary** 中缩小「DOMINANT_CONFLICT → 禁止 open」的适用范围（例如仅当 directional_alignment 为 CONFLICT 且 mid_term 也拥挤时才禁止 open）。

### 2. 仅因「短期拥挤」被拦（提示词可优化）

- 当 **forbidden_actions 不包含 "open"** 且 **structural_clarity != DOMINANT_CONFLICT** 时，若仍因「短期拥挤风险高」被 NO_ACTION，则完全由**本 Agent 的规则 8** 决定。
- 若此时 **mid_term 与 long_term 均不拥挤**（mid_term.crowding_risk == "low"、long_term.zone == "low"），且 **方向对齐、信号强度足够**（如 l1_total_score >= 30），从逻辑上属于「可降杠杆试探」的可做单，不应一律禁止。

## 四、已做的提示词修改（避免误杀可做单）

1. **新增【允许开仓的例外】**  
   - 当：仅 short_term.crowding_risk == "high"，且 mid_term.crowding_risk == "low"，long_term.zone == "low"，directional_alignment.mid_term 为 ALIGNED/NEUTRAL，l1_total_score 绝对值 >= 30，且 **forbidden_actions 不包含 "open"、structural_clarity != DOMINANT_CONFLICT** 时，**不**触发规则 8，应输出 OPEN_* 并**强制** leverage 5~10。

2. **规则 8 的例外显式化**  
   - 规则 8 中明确：若同时满足上述「允许开仓例外」条件，则**不**触发本规则，应开仓并降杠杆。  
   - 并强调：realtime_market_data 为空或默认时，不得以「实时数据不支持」为由否决，仅按结构判断；符合例外即应开仓。

3. **开仓条件与例外并列**  
   - 在【开仓条件】中写明：满足「常规 1~6」且不触发硬门控（或触发规则 8 但满足例外）时可开仓；**或**直接满足【允许开仓的例外】1~6 条时，即输出 OPEN_*、leverage 5~10。

## 五、后续建议

1. **观察下一阶段日志**  
   - 在「mid 低、long 低、信号>=30、上游未禁止 open」的情况下，是否会出现 OPEN_* 且 leverage 5~10；若仍大量 NO_ACTION，再查是否 LLM 未正确识别例外条件。

2. **若仍大量「forbidden_actions 包含 open」**  
   - 需要在上游排查：SignalValidation 在「仅短期拥挤、中期对齐」时是否不应输出 DOMINANT_CONFLICT；或 ExecutionBoundary 是否应仅在「真正结构冲突」时禁止 open，而不是只要 DOMINANT_CONFLICT 就禁止。

3. **数据层面**  
   - 当前日志中，多数标的的 short_term.crowding_risk 为 "high"。若 pre_decision_structure 的产出逻辑较保守，可能长期处于「几乎全部 short 高」的状态，此时「允许开仓例外」主要依赖 **mid_term 与 long_term 为 low** 的个案；可同时回顾生成 crowding_risk 的上游逻辑是否过严。

---

## 六、并发瓶颈与「感觉还是有问题」的根因（12:17 段日志）

### 6.1 并发 20 导致事件排队、无法实时跑

- 日志中大量 **`[等待] 并发已满(20)`**：新 L1 事件在 `while len(self.running_workflows) >= self.MAX_CONCURRENT` 里轮询等待，每 5 秒打一次日志。
- 单条事件（如 TAKEUSDT single_signal_boll.1772514478907）从 12:18:08 开始等，直到 12:20:05 才有 slot 被 180s 超时回收，**实际等待约 2 分钟**才进入 workflow，严重滞后。
- 原因：**MAX_CONCURRENT 默认 20**，而单次 workflow（SignalValidation + TradeDecision + LLM）耗时从数秒到数十秒不等，20 个槽位被占满后，后续事件只能排队，无法「实时」处理。

**已做修改**：`trade_listen_main.py` 中 **MAX_CONCURRENT 默认值由 20 改为 200**（仍可通过环境变量 `TRADE_L1_MAX_CONCURRENT` 覆盖）。这样多数 L1 事件可以立即拿到并发名额、实时跑起来，而不是长时间卡在「并发已满」循环里。

### 6.2 为何「允许开仓例外」几乎从不触发？

- 从 **trade_ai_reasoning_20260307.log** 的推理输入可见：**所有样本**里 `short_term.structural_risks.crowding_risk` 均为 `"high"`，且绝大多数 `mid_term.structural_risks.crowding_risk` 也为 `"high"`，`long_term.structural_context.crowding_percentile.zone` 多为 `"elevated"`。
- 「允许开仓例外」要求：short 高 + **mid 低** + **long 低** + 方向对齐 + l1_score >= 30 + 上游未禁止。当前 **pre_decision_structure 的数据里几乎从未出现「mid 低且 long 低」**，因此例外条件在数据层面就不满足，不是提示词没写对。
- 若希望更多单子能开出来，需要：
  1. **上游**：放宽或校准 pre_decision_structure / SignalValidation 里对 mid_term.crowding_risk、long_term.zone 的赋值，让「mid 低、long 低」的 case 有一定比例出现；或  
  2. **规则**：在可控前提下适当放宽「允许开仓例外」（例如 long_term 为 elevated 但 mid 为 low 时也允许降杠杆开仓），需结合实盘风险意愿决定。
