# Release Handoff 2026-03-12

更新时间：2026-03-12

## 1) 基线指纹

- branch: `master`
- baseline tag: `refactor-guard-baseline-20260312`
- baseline commit: use command output (`git rev-parse --short refactor-guard-baseline-20260312`)

## 2) 发布前最小验收

```bash
bash tools/ci/verify_quick.sh
bash tools/ci/new_arch_guards_full.sh --quick
```

期望：全部通过。

或直接使用一键检查：

```bash
bash tools/local/check_release_ready.sh
```

## 3) 标准排障命令

```bash
bash tools/local/check_contract_change_bundle_guard.sh --show-detected-versions
rg -n "^\[CI_GUARD\]" quick_strict.log quick_lenient.log full_guard.log
cat guard_summary.quick_strict.log guard_summary.quick_lenient.log guard_summary.full.log
```

## 4) 快速回滚

```bash
git checkout refactor-guard-baseline-20260312
```

## 5) 交接确认项

- [x] baseline tag 与 `master` 对齐
- [x] baseline 文档与 tag 指向一致
- [x] contract/docs 守卫链路通过
- [x] readyz 门禁阈值已记录：
  - regression：`MAX_AGENT_READYZ_LEVEL`、`REQUIRE_AGENT_READYZ_REPORT`
  - nightly：`MAX_AGENT_READYZ_LEVEL`、`REQUIRE_AGENT_READYZ_REPORT`
- [x] 聚合报告 readyz 字段已核对：
  - `agent_readyz_status_level`
  - `agent_readyz_report_count`
  - `agent_readyz_error_count`
  - `agent_readyz_errors`

## 6) 滚动更新记录（2026-03-13）

- 已将 baseline tag `refactor-guard-baseline-20260312` 重新对齐到当日 `HEAD`。
- 已执行：`bash tools/local/verify_quick.sh`，结果通过。
- 已执行：`bash tools/ci/new_arch_guards_full.sh --quick`，结果通过。
- 已执行：`bash tools/local/check_release_ready.sh`，结果通过。
