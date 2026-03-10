# event_center_new CI 手册

本文件用于统一 `event_center_new` 的 CI 触发方式、守卫矩阵与失败处置路径。

## 1. CI 触发矩阵

- quick（严格 + 宽松并行）：
  - 工作流：`.github/workflows/event-center-quick.yml`
  - 触发：`pull_request` / `push(main)`（按路径过滤）
- full（全量严格）：
  - 工作流：`.github/workflows/event-center-full.yml`
  - 触发：`workflow_dispatch` / 每日定时 `cron`

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

## 4. 常见排障顺序

1. 先复现同模式失败（quick strict / quick lenient / full strict）。
2. 再拆分成 `schema -> runtime -> wiring` 三组守卫定位。
3. 修复后至少回归对应模式一次。
