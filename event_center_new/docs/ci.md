# event_center_new CI 手册

本文件用于统一 `event_center_new` 的 CI 触发方式、守卫矩阵与失败处置路径。

## 1. CI 触发矩阵

- 复用初始化 action：`.github/actions/setup-utaker-python/action.yml`
- quick（严格 + 宽松并行）：
  - 工作流：`.github/workflows/event-center-quick.yml`
  - 触发：`pull_request` / `push(main)`（按路径过滤）
- 失败诊断：
    - strict job 自动上传 `event-center-quick-strict-diagnostics`（`quick_strict.log`）
    - lenient job 自动上传 `event-center-quick-lenient-diagnostics`（`quick_lenient.log`）
    - 失败收敛步骤会打印 `rg -n "FAIL_CODE=" ...` 的日志定位提示
- full（全量严格）：
  - 工作流：`.github/workflows/event-center-full.yml`
  - 触发：`workflow_dispatch` / 每日定时 `cron`
- 失败诊断：自动上传 artifact `event-center-full-diagnostics`（包含 `full_guard.log`）
  - 失败收敛步骤会打印 `rg -n "FAIL_CODE=" full_guard.log` 的日志定位提示

## 2. 本地等价命令

1. quick strict
   - `bash scripts/ci_event_center_quick_strict.sh`
2. quick lenient
   - `bash scripts/ci_event_center_quick_lenient.sh`
3. full strict
   - `bash scripts/check_new_arch_guards.sh --event-center-only --strict-wiring`

## 3. 失败分类与定位

1. 契约/Schema 失败
   - `bash scripts/check_event_center_contract_schema_guards.sh`
2. Runtime 失败
   - `bash scripts/check_event_center_runtime_family_guards.sh`
3. 接线失败
   - `bash scripts/check_event_center_guard_wiring.sh --strict --show-links`

失败码对照（聚合守卫统一输出 `FAIL_CODE=...`）：

- `EC_GUARD_SCHEMA_FAILED`：契约/Schema 子守卫失败
- `EC_GUARD_RUNTIME_FAILED`：Runtime 子守卫失败
- `EC_GUARD_WIRING_FAILED`：接线子守卫失败
- `EC_GUARD_CI_WORKFLOW_FAILED`：CI workflow 静态守卫失败

## 4. 常见排障顺序

1. 先复现同模式失败（quick strict / quick lenient / full strict）。
2. 再拆分成 `schema -> runtime -> wiring` 三组守卫定位。
3. 修复后至少回归对应模式一次。

## 5. CI 工作流守卫

- 脚本：`scripts/check_event_center_ci_workflow_guard.sh`
- 作用：静态校验 quick/full workflow 仍包含失败诊断 artifact 上传和显式失败收敛步骤。
- 接入：已纳入 `scripts/check_event_center_contract_guards.sh` 的 quick/full 路径。

## 6. Artifact 日志锚点（下载后）

1. quick strict / quick lenient
   - 日志文件：`quick_strict.log` / `quick_lenient.log`
   - 关键锚点：
     - `event_center 契约/Schema 守卫`
     - `event_center Runtime 守卫`
     - `event_center 守卫接线检查`
     - `event_center CI workflow 守卫`
2. full strict
   - 日志文件：`full_guard.log`
   - 关键锚点：
     - `event_center 契约/Schema 守卫（全量）`
     - `event_center Runtime 守卫（全量）`
     - `event_center 守卫接线检查（全量）`
     - `event_center CI workflow 守卫（全量）`

建议定位命令（本地）：

```bash
rg -n "契约/Schema|Runtime|守卫接线|CI workflow 守卫|\\[失败\\]" quick_strict.log
rg -n "契约/Schema|Runtime|守卫接线|CI workflow 守卫|\\[失败\\]" full_guard.log
rg -n "FAIL_CODE=" quick_strict.log
rg -n "FAIL_CODE=" full_guard.log
```
