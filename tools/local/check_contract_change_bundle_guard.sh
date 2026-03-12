#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'USAGE'
用法:
  bash tools/local/check_contract_change_bundle_guard.sh
  CONTRACT_BUNDLE_BASE_REF=<git-ref> bash tools/local/check_contract_change_bundle_guard.sh

说明:
  - 当检测到 services/*/docs/*.schema.json 或 schema_mapping.json 发生变更时，
    强制校验“契约变更四件套”是否同时更新：
    1) docs/CONTRACT_INDEX.md
    2) 模块契约文档（api/schema/runner_output_contract）
    3) 模块迁移文档（migration/refactor/REFACTOR_PLAN_V2）
    4) 守卫或测试（tools/local/check_*guard.sh 或 verification/*）
  - 对比基线默认使用 HEAD~1，可通过 CONTRACT_BUNDLE_BASE_REF 覆盖。
USAGE
  exit 0
fi

BASE_REF="${CONTRACT_BUNDLE_BASE_REF:-HEAD~1}"
if ! git rev-parse --verify "${BASE_REF}" >/dev/null 2>&1; then
  echo "[提示] 无法解析基线 ${BASE_REF}，跳过四件套差异校验。"
  exit 0
fi

CHANGED_FILES="$(git diff --name-only "${BASE_REF}"...HEAD || true)"
if [[ -z "${CHANGED_FILES}" ]]; then
  echo "[通过] 基线对比无文件变更，跳过四件套校验。"
  exit 0
fi

schema_changed_services="$(
  printf '%s\n' "${CHANGED_FILES}" \
    | rg '^services/.+/docs/.+\.schema\.json$|^services/.+/docs/schema_mapping\.json$' \
    | sed -E 's#^services/([^/]+)/.*#\1#' \
    | sort -u || true
)"

if [[ -z "${schema_changed_services}" ]]; then
  echo "[通过] 未检测到 schema 变更，无需执行四件套校验。"
  exit 0
fi

echo "[1/2] 检测到 schema 变更服务："
printf '%s\n' "${schema_changed_services}" | sed 's/^/  - /'

check_changed_exact() {
  local path="$1"
  printf '%s\n' "${CHANGED_FILES}" | rg -x "${path}" >/dev/null 2>&1
}

check_changed_regex() {
  local pattern="$1"
  printf '%s\n' "${CHANGED_FILES}" | rg "${pattern}" >/dev/null 2>&1
}

fail=0
echo "[2/2] 校验契约变更四件套"
while IFS= read -r svc; do
  [[ -z "${svc}" ]] && continue

  contract_doc=""
  migration_doc=""
  guard_or_test_regex=""
  case "${svc}" in
    feature_service)
      contract_doc="services/feature_service/docs/api.md"
      migration_doc="services/feature_service/docs/migration.md"
      guard_or_test_regex='^tools/local/check_feature_.*guard\.sh$|^verification/.*/feature_service/.*\.(py|sh|ya?ml)$'
      ;;
    market_state_engine)
      contract_doc="services/market_state_engine/docs/api.md"
      migration_doc="services/market_state_engine/docs/migration.md"
      guard_or_test_regex='^tools/local/check_market_state_.*guard\.sh$|^tools/local/check_state_to_agent_contract_guard\.sh$|^verification/.*/market_state_engine/.*\.(py|sh|ya?ml)$'
      ;;
    event_center_new)
      contract_doc="services/event_center_new/docs/schema.md"
      migration_doc="services/event_center_new/docs/refactor.md"
      guard_or_test_regex='^tools/local/check_event_center_.*guard.*\.sh$|^verification/.*/event_center_new/.*\.(py|sh|ya?ml)$'
      ;;
    agent_server_new)
      contract_doc="services/agent_server_new/docs/runner_output_contract.md"
      migration_doc="services/agent_server_new/docs/REFACTOR_PLAN_V2.md"
      guard_or_test_regex='^tools/local/check_state_to_agent_contract_guard\.sh$|^tools/local/check_agent_to_execution_guard\.sh$|^verification/.*/agent_server_new/.*\.(py|sh|ya?ml)$'
      ;;
    execution_service)
      contract_doc="services/execution_service/docs/api.md"
      migration_doc="services/execution_service/docs/migration.md"
      guard_or_test_regex='^tools/local/check_execution_.*guard\.sh$|^tools/local/check_agent_to_execution_guard\.sh$|^verification/.*/execution_service/.*\.(py|sh|ya?ml)$'
      ;;
    *)
      echo "[失败] 未知服务: ${svc}"
      fail=1
      continue
      ;;
  esac

  missing=()
  check_changed_exact 'docs/CONTRACT_INDEX.md' || missing+=("docs/CONTRACT_INDEX.md")
  check_changed_exact "${contract_doc}" || missing+=("${contract_doc}")
  check_changed_exact "${migration_doc}" || missing+=("${migration_doc}")
  check_changed_regex "${guard_or_test_regex}" || missing+=("guard_or_test(${svc})")

  if [[ ${#missing[@]} -gt 0 ]]; then
    echo "[失败] ${svc} 检测到 schema 变更，但四件套未齐全："
    printf '  - %s\n' "${missing[@]}"
    fail=1
  else
    echo "[通过] ${svc} 四件套齐全。"
  fi
done <<< "${schema_changed_services}"

if [[ "${fail}" -ne 0 ]]; then
  exit 1
fi

echo "[通过] 契约变更四件套守卫检查完成。"
