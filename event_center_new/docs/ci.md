# event_center_new CI 手册

本文件用于统一 `event_center_new` 的 CI 触发方式、守卫矩阵与失败处置路径。

## 1. CI 触发矩阵

- 复用初始化 action：`.github/actions/setup-utaker-python/action.yml`
- quick（严格 + 宽松并行）：
  - 工作流：`.github/workflows/event-center-quick.yml`
  - 触发：`pull_request` / `push(main)`（按路径过滤）
- 失败诊断：
    - strict job 自动上传 `event-center-quick-strict-diagnostics`（目录 artifact，至少包含 `quick_strict.log`）
    - lenient job 自动上传 `event-center-quick-lenient-diagnostics`（目录 artifact，至少包含 `quick_lenient.log`）
    - 失败收敛步骤会打印“先 `pwd`、`ls -la .`，再 `rg -n "FAIL_CODE=" ...`”的日志定位提示
- full（全量严格）：
  - 工作流：`.github/workflows/event-center-full.yml`
  - 触发：`workflow_dispatch` / 每日定时 `cron`
- 失败诊断：自动上传 artifact `event-center-full-diagnostics`（包含 `full_guard.log`）
  - 失败收敛步骤会打印“先 `pwd`、`ls -la .`，再 `rg -n "FAIL_CODE=" full_guard.log`”的日志定位提示

## 2. 本地等价命令

1. quick strict
   - `bash scripts/ci_event_center_quick_strict.sh`
2. quick lenient
   - `bash scripts/ci_event_center_quick_lenient.sh`
3. full strict
   - `bash scripts/ci_event_center_full_strict.sh`
4. 新架构入口（event_center quick/only，含告警入口守卫）
   - `bash scripts/check_new_arch_guards.sh --event-center-quick`
   - `bash scripts/check_new_arch_guards.sh --event-center-only`
   - 说明：两者都会先执行 `scripts/check_alert_codes_entry_guard.sh`，再执行 event_center 守卫聚合

日志头部约定（quick/full 通用）：
- `[CI_META] run_mode=...`
- `[CI_META] git_sha=...`
- `[CI_META] runtime_config_version=...`
- `[CI_META] ts_utc=...`

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
- `EC_GUARD_CI_DOC_FAILED`：CI 文档快照守卫失败
- `EC_GUARD_HELP_SNAPSHOT_SYNC_FAILED`：`--help` 与快照关键行文件不一致

可用 `bash scripts/check_event_center_contract_guards.sh --help` 查看同一份失败码清单。
当前帮助输出快照：

```text
用法:
  bash scripts/check_event_center_contract_guards.sh
  bash scripts/check_event_center_contract_guards.sh --quick
  bash scripts/check_event_center_contract_guards.sh [--quick] [--strict-wiring|--lenient-wiring]

失败码（子守卫失败时输出 FAIL_CODE=...）:
  EC_GUARD_SCHEMA_FAILED
  EC_GUARD_RUNTIME_FAILED
  EC_GUARD_WIRING_FAILED
  EC_GUARD_CI_WORKFLOW_FAILED
  EC_GUARD_CI_DOC_FAILED
  EC_GUARD_HELP_SNAPSHOT_SYNC_FAILED
```

## 4. 常见排障顺序

1. 先复现同模式失败（quick strict / quick lenient / full strict）。
   - 若使用新架构入口（`check_new_arch_guards.sh --event-center-*`），先确认告警入口守卫是否失败。
2. 再拆分成 `schema -> runtime -> wiring` 三组守卫定位。
3. 修复后至少回归对应模式一次。

## 5. CI 工作流守卫

- 脚本：`scripts/check_event_center_ci_workflow_guard.sh`
- 作用：静态校验 quick/full workflow 仍包含失败诊断 artifact 上传、显式失败收敛步骤和“最短排障命令串”提示。
- 接入：已纳入 `scripts/check_event_center_contract_guards.sh` 的 quick/full 路径。

## 6. CI 文档快照守卫

- 脚本：`scripts/check_event_center_ci_doc_snapshot_guard.sh`
- 作用：校验 `event_center_new/docs/ci.md` 中 `--help` 快照与“最短排障命令串”关键行未漂移。
- 附加校验：快照关键行文件必须非空且无重复行。
- 附加校验：
  - 快照关键行文件禁止全角空格（防止不可见字符漂移）
  - `event_center_new/docs/ci_triage_snapshot_lines.txt` 必须 ASCII-only
- 关键行来源：
  - `event_center_new/docs/ci_help_snapshot_lines.txt`
  - `event_center_new/docs/ci_triage_snapshot_lines.txt`
- 接入：已纳入 `scripts/check_event_center_contract_guards.sh` 的 quick/full 路径。

## 7. 帮助快照同步守卫

- 脚本：`scripts/check_event_center_help_snapshot_sync_guard.sh`
- 作用：校验 `scripts/check_event_center_contract_guards.sh --help` 完整输出块与失败码顺序均与快照一致。
- 快照来源：
  - `event_center_new/docs/ci_help_block_snapshot.txt`（完整输出块）
  - `event_center_new/docs/ci_help_snapshot_lines.txt`（失败码关键行）
- 接入：已纳入 `scripts/check_event_center_contract_guards.sh` 的 quick/full 路径。

## 8. Artifact 日志锚点（下载后）

推荐解压目录结构示例：

```text
./
├── quick_strict.log
├── quick_lenient.log
└── full_guard.log
```

说明：
- quick strict 失败时，至少会有 `quick_strict.log`
- quick lenient 失败时，至少会有 `quick_lenient.log`
- full strict 失败时，至少会有 `full_guard.log`

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
pwd
ls -la .
rg -n "契约/Schema|Runtime|守卫接线|CI workflow 守卫|\\[失败\\]" quick_strict.log
rg -n "契约/Schema|Runtime|守卫接线|CI workflow 守卫|\\[失败\\]" full_guard.log
rg -n "FAIL_CODE=" quick_strict.log
rg -n "FAIL_CODE=" full_guard.log
```

最短排障命令串（可复制）：

```bash
# quick strict / quick lenient
pwd && ls -la . && rg -n "FAIL_CODE=" quick_strict.log quick_lenient.log

# full strict
pwd && ls -la . && rg -n "FAIL_CODE=" full_guard.log
```

## 9. 基线通过记录

模板文件：`event_center_new/docs/ci_baseline_template.md`

| date | command | mode | result | commit |
|---|---|---|---|---|
| 2026-03-11 | `bash scripts/check_new_arch_guards.sh --event-center-quick` | `quick` | `pass` | `eebe63f` |
| 2026-03-11 | `bash scripts/check_new_arch_guards.sh --event-center-only` | `full` | `pass` | `eebe63f` |
| 2026-03-11 | `bash scripts/check_new_arch_guards.sh --event-center-quick` | `quick` | `pass` | `e335162` |
| 2026-03-11 | `bash scripts/check_new_arch_guards.sh --event-center-only` | `full` | `pass` | `e335162` |
