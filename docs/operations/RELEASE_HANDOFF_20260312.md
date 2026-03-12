# Release Handoff 2026-03-12

更新时间：2026-03-12

## 1) 基线指纹

- branch: `master`
- baseline tag: `refactor-guard-baseline-20260312`
- baseline commit: `921aed2`

## 2) 发布前最小验收

```bash
bash tools/ci/verify_quick.sh
bash tools/ci/new_arch_guards_full.sh --quick
```

期望：全部通过。

## 3) 标准排障命令

```bash
bash tools/local/check_contract_change_bundle_guard.sh --show-detected-versions
```

## 4) 快速回滚

```bash
git checkout refactor-guard-baseline-20260312
```

## 5) 交接确认项

- [x] baseline tag 与 `master` 对齐
- [x] baseline 文档与 tag 指向一致
- [x] contract/docs 守卫链路通过
