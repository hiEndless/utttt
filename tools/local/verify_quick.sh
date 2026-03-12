#!/usr/bin/env bash
set -euo pipefail

WITH_VERIFICATION_API_SCHEMA_CHECK=0
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
USAGE
  exit 0
fi

CMD=(bash tools/ci/verify_quick.sh)
if ((${#PASS_ARGS[@]} > 0)); then
  CMD+=("${PASS_ARGS[@]}")
fi
"${CMD[@]}"

if [[ "$WITH_VERIFICATION_API_SCHEMA_CHECK" == "1" ]]; then
  if test -x ./venv/bin/pytest; then
    ./venv/bin/pytest -q \
      verification/text/test_verification_api.py::test_verification_api_summary_schema_validation_enabled_passes
  else
    python3 -m pytest -q \
      verification/text/test_verification_api.py::test_verification_api_summary_schema_validation_enabled_passes
  fi
fi
