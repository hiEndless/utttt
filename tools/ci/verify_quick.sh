#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'USAGE'
Usage:
  bash tools/ci/verify_quick.sh

Description:
  CI quick 验证入口。执行结构守卫、docs/contracts 聚合守卫、链路 quick suite 与语义审计后处理。

Environment Switches (local debug only):
  VERIFY_QUICK_SKIP_RELEASE_BASELINE_ALIGNMENT=1
  VERIFY_QUICK_SKIP_SEMANTIC_CRITICAL=1

CI Hard Constraints:
  当 CI=true 或 GITHUB_ACTIONS=true 时，禁止启用上述 skip 开关；若启用会直接失败（exit 2）。

Failure Codes:
  exit 1  任一守卫/测试失败
  exit 2  CI 环境下启用了禁止的 skip 开关
USAGE
  exit 0
fi

if (($# > 0)); then
  echo "[failed] unsupported args: $*"
  echo "hint: run 'bash tools/ci/verify_quick.sh --help'"
  exit 1
fi

# CI 强约束：禁止在 CI 环境通过 skip 开关绕过关键守卫。
if [[ "${CI:-}" == "true" || "${GITHUB_ACTIONS:-}" == "true" ]]; then
  if [[ "${VERIFY_QUICK_SKIP_RELEASE_BASELINE_ALIGNMENT:-0}" == "1" ]]; then
    echo "[failed] VERIFY_QUICK_SKIP_RELEASE_BASELINE_ALIGNMENT=1 is not allowed in CI"
    exit 2
  fi
  if [[ "${VERIFY_QUICK_SKIP_SEMANTIC_CRITICAL:-0}" == "1" ]]; then
    echo "[failed] VERIFY_QUICK_SKIP_SEMANTIC_CRITICAL=1 is not allowed in CI"
    exit 2
  fi
fi

bash tools/local/check_structure.sh
bash tools/local/check_script_compat_whitelist.sh
if ! bash tools/local/check_docs_contracts_bundle.sh; then
  echo "[hint] docs/contracts bundle 失败，建议执行："
  echo "       bash tools/local/check_contract_change_bundle_guard.sh --show-detected-versions"
  echo "[hint] 自动输出版本探测值（用于 CI 日志/artifact 排障）："
  bash tools/local/check_contract_change_bundle_guard.sh --show-detected-versions || true
  exit 1
fi
# 显式执行来源语义守卫，保证 quick 日志可直接展示该门禁状态。
# 说明：docs/contracts bundle 内也会执行同一守卫，这里属于“可见性优先”的有意重复。
bash tools/local/check_source_semantics_guard.sh
if [[ "${VERIFY_QUICK_SKIP_RELEASE_BASELINE_ALIGNMENT:-0}" == "1" ]]; then
  echo "[warn] skip release baseline alignment guard by VERIFY_QUICK_SKIP_RELEASE_BASELINE_ALIGNMENT=1"
else
  bash tools/local/check_release_baseline_alignment.sh
fi
bash tools/local/check_prod_provider_modes_guard.sh
bash tools/ci/verify_all.sh --quick
bash tools/local/sync_contract_indexes.sh
bash tools/local/audit_semantics.sh
if [[ "${VERIFY_QUICK_SKIP_SEMANTIC_CRITICAL:-0}" == "1" ]]; then
  echo "[warn] skip semantic critical warning guard by VERIFY_QUICK_SKIP_SEMANTIC_CRITICAL=1"
else
  bash tools/local/check_semantic_critical_warning_guard.sh
fi
