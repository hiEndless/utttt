#!/usr/bin/env bash
set -euo pipefail

WITH_VERIFICATION_API_SCHEMA_CHECK=0
SKIP_SEMANTIC_CRITICAL_WARNING_GUARD=0
SKIP_RELEASE_BASELINE_ALIGNMENT=0
SHOW_HELP=0
PASS_ARGS=()

while (($# > 0)); do
  case "$1" in
    --help|-h)
      SHOW_HELP=1
      shift
      ;;
    --with-verification-api-schema-check)
      WITH_VERIFICATION_API_SCHEMA_CHECK=1
      shift
      ;;
    --skip-semantic-critical-warning-guard)
      SKIP_SEMANTIC_CRITICAL_WARNING_GUARD=1
      shift
      ;;
    --skip-release-baseline-alignment)
      SKIP_RELEASE_BASELINE_ALIGNMENT=1
      shift
      ;;
    *)
      PASS_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ "$SHOW_HELP" == "1" ]]; then
  cat <<'USAGE'
Usage:
  bash tools/local/verify_quick.sh [options] [args...]

Description:
  本地 quick 验证入口，代理到：
    bash tools/ci/verify_quick.sh [args...]

Options:
  --with-verification-api-schema-check   追加执行 verification API summary schema 开关校验测试
  --skip-semantic-critical-warning-guard 跳过 semantic critical warning guard（仅本地调试）
  --skip-release-baseline-alignment      跳过 release baseline 对齐校验（仅本地调试）
USAGE
  exit 0
fi

ENV_PREFIX=()
if [[ "$SKIP_SEMANTIC_CRITICAL_WARNING_GUARD" == "1" ]]; then
  ENV_PREFIX+=(VERIFY_QUICK_SKIP_SEMANTIC_CRITICAL=1)
fi
if [[ "$SKIP_RELEASE_BASELINE_ALIGNMENT" == "1" ]]; then
  ENV_PREFIX+=(VERIFY_QUICK_SKIP_RELEASE_BASELINE_ALIGNMENT=1)
fi
CMD=(bash tools/ci/verify_quick.sh)
if ((${#PASS_ARGS[@]} > 0)); then
  CMD+=("${PASS_ARGS[@]}")
fi
if ((${#ENV_PREFIX[@]} > 0)); then
  env "${ENV_PREFIX[@]}" "${CMD[@]}"
else
  "${CMD[@]}"
fi

if [[ "$WITH_VERIFICATION_API_SCHEMA_CHECK" == "1" ]]; then
  if test -x ./venv/bin/pytest; then
    ./venv/bin/pytest -q \
      verification/text/test_verification_api.py::test_verification_api_summary_schema_validation_enabled_passes
  else
    python3 -m pytest -q \
      verification/text/test_verification_api.py::test_verification_api_summary_schema_validation_enabled_passes
  fi
fi
