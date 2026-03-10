#!/usr/bin/env bash
set -euo pipefail

echo "[1/4] 校验 runtime bump tool --help"
help_text="$(bash scripts/bump_event_center_runtime_version.sh --help)"
if ! echo "$help_text" | rg -q -- "--print-current-version"; then
  echo "[失败] --help 缺少 --print-current-version"
  exit 1
fi
if ! echo "$help_text" | rg -q -- "--dry-run"; then
  echo "[失败] --help 缺少 --dry-run"
  exit 1
fi
if ! echo "$help_text" | rg -q -- "--check-clean"; then
  echo "[失败] --help 缺少 --check-clean"
  exit 1
fi
if ! echo "$help_text" | rg -q -- "--apply-from-env-table"; then
  echo "[失败] --help 缺少 --apply-from-env-table"
  exit 1
fi

echo "[2/4] 校验 --print-current-version"
current_version="$(bash scripts/bump_event_center_runtime_version.sh --print-current-version)"
doc_version="$(rg -o 'runtime_config_version:\s*[A-Za-z0-9._-]+' event_center_new/docs/runtime.md | head -n1 | sed -E 's/.*runtime_config_version:\s*//' | xargs)"
if [[ -z "$doc_version" ]]; then
  echo "[失败] 未能从 runtime.md 解析版本号"
  exit 1
fi
if [[ "$current_version" != "$doc_version" ]]; then
  echo "[失败] --print-current-version 与 runtime.md 不一致 cli=$current_version doc=$doc_version"
  exit 1
fi

echo "[3/4] 校验 --dry-run + --apply-from-env-table"
dry_run_out="$(bash scripts/bump_event_center_runtime_version.sh event-center-runtime-v999 "guard dry run" --apply-from-env-table --dry-run)"
if ! echo "$dry_run_out" | rg -q -- "dry-run"; then
  echo "[失败] dry-run 输出不包含预期提示"
  exit 1
fi
if ! echo "$dry_run_out" | rg -q -- "event-center-runtime-v999"; then
  echo "[失败] dry-run 输出不包含目标版本"
  exit 1
fi

echo "[4/4] 校验 --check-clean"
if git diff --quiet && git diff --cached --quiet; then
  # 工作区干净时，check-clean 不应阻断。
  bash scripts/bump_event_center_runtime_version.sh event-center-runtime-v999 "guard clean check" --check-clean --dry-run >/dev/null
else
  # 工作区非干净时，check-clean 应返回非 0。
  if bash scripts/bump_event_center_runtime_version.sh event-center-runtime-v999 "guard clean check" --check-clean --dry-run >/dev/null 2>&1; then
    echo "[失败] 脏工作区下 --check-clean 未触发失败"
    exit 1
  fi
fi

echo "[通过] event_center runtime bump tool 守卫检查完成。"
