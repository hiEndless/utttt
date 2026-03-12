# UTaker

精简入口文档（导航版）。

## 1. 仓库结构

- 业务服务：`services/`
- 跨服务契约：`contracts/`
- 验证层：`verification/`
- 开发与 CI 脚本：`tools/`
- 架构与运维文档：`docs/`

## 2. 验证入口（推荐）

- quick（本地代理入口）：
  - `bash tools/local/verify_quick.sh`
  - 实际执行：`bash tools/ci/verify_quick.sh`
- full（本地代理入口）：
  - `bash tools/local/verify_full.sh`
  - 实际执行：`bash tools/ci/new_arch_guards_full.sh`

## 3. 常用脚本

- 生成 memory summary 报告：
  - `bash tools/local/run_agent_memory_summary_report.sh --help`
- 聚合 verification 报告：
  - `bash tools/local/verify_report_aggregate.sh --help`
- 聚合 + 阈值检查：
  - `bash tools/local/aggregate_and_check.sh --help`

## 4. 文档入口（Canonical）

- 架构总览：`docs/architecture/ARCHITECTURE_NEW.md`
- 契约索引：`docs/CONTRACT_INDEX.md`
- 契约速查：`docs/contracts/CONTRACTS_QUICK_REF.md`
- 运维索引：`docs/operations/index.md`

> 说明：详细内容以 `docs/` 下对应 canonical 文档为准，本文件只做导航，不维护分叉细节。

