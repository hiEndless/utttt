# Verification Script Inventory

更新时间：2026-03-12

## 1. 当前状态

- `scripts/` 目录中的验证兼容壳已全部下线。
- 验证入口统一收敛到 `tools/local/*`、`tools/ci/*` 与 `verification/guards/*`。

## 2. 主入口

- 全量守卫：`tools/ci/new_arch_guards_full.sh`
- 快速验证：`tools/ci/verify_quick.sh`
- 脚本白名单检查：`tools/local/check_script_compat_whitelist.sh`

## 3. 历史映射

历史 `scripts/*` 到新入口的映射保留在：
- `verification/migration_map.yaml`

该映射仅用于审计与追溯，不再作为运行入口。
