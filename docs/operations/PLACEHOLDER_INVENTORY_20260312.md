# Placeholder Inventory 2026-03-12

更新时间：2026-03-12

## 1. 审计范围

- 目录：`services/*`（排除 `docs/`、`text/`、`TASKS.md`、`README.md`）
- 关键词：`TODO/FIXME/TBD/placeholder/stub/NotImplementedError/pass/待实现/占位/伪代码`

## 2. 结论

- 运行时代码中，未发现“未实现占位逻辑”关键字命中。
- 当前命中的 `pass` 语义为状态枚举值（`risk_check.status = "pass"`），不是占位代码。
- 剩余 `stub/mock/noop` 主要位于：
  - 测试夹具（`verification/fixtures/*`）
  - 文档示例（`docs/*`）
  - 可控回退适配器（如 execution/agent 的非 prod provider）

## 3. 仍需关注的“准占位”资产

1. `services/execution_service/adapters/stub_state_providers.py`
- 角色：联调与测试 fallback provider。
- 风险：若环境门禁配置失效，可能被误用于生产。
- 现状：`prod` profile 已有模式门禁（默认 redis/exchange）。

2. `services/agent_server_new/adapters/active_events_stub.py`
- 角色：active events fallback。
- 风险：事件源不可用时语义降级。
- 现状：`prod` profile 已强制 redis provider，不允许 stub。

3. `services/agent_server_new/adapters/position_context_stub.py`
- 角色：仓位上下文 fallback。
- 风险：策略使用不完整仓位信息。
- 现状：默认已切到 http provider，stub 非默认路径。

## 4. 建议的下一步清理

1. 为上述 3 类 fallback provider 增加统一“非 prod 断言”审计脚本（可并入 `verification/guards`）。
2. 把 `stub/mock/noop` 的允许清单显式化（路径 + 使用场景 + 退役计划）。
3. 在 `verify_quick` 中加入“fallback provider 配置快照”输出，便于发布前人工确认。

## 5. 复用命令

```bash
rg -n "\\bTODO\\b|\\bFIXME\\b|\\bTBD\\b|\\bplaceholder\\b|\\bstub\\b|NotImplementedError|待实现|占位|伪代码|\\bpass\\b" \
  services --glob '!**/docs/**' --glob '!**/text/**' --glob '!**/TASKS.md' --glob '!**/README.md' --glob '!**/tests/**' -S
```
