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
  - 当检测到 event_center runtime 版本锚点（event_center_runtime_config_version）
    发生变更时，强制校验 event_center 版本联动四件套：
    1) docs/CONTRACT_INDEX.md
    2) contracts/versions/manifest.yaml
    3) services/event_center_new/version.py 与 services/event_center_new/docs/runtime.md
    4) 守卫或测试（event_center guard 或 manifest 对齐测试）
  - 对比基线默认使用 HEAD~1，可通过 CONTRACT_BUNDLE_BASE_REF 覆盖。

示例:
  # 场景1：仅改 event_center runtime 版本常量，会被拦截（四件套不全）
  #   services/event_center_new/version.py: EVENT_CENTER_RUNTIME_CONFIG_VERSION v1 -> v2
  # 场景2：runtime 版本升版并同步四件套，可通过
  #   同步更新 docs/CONTRACT_INDEX.md + contracts/versions/manifest.yaml +
  #   services/event_center_new/version.py + services/event_center_new/docs/runtime.md
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

check_changed_exact() {
  local path="$1"
  printf '%s\n' "${CHANGED_FILES}" | rg -x "${path}" >/dev/null 2>&1
}

check_changed_regex() {
  local pattern="$1"
  printf '%s\n' "${CHANGED_FILES}" | rg "${pattern}" >/dev/null 2>&1
}

extract_index_runtime_version_from_rev() {
  local rev="$1"
  git show "${rev}:docs/CONTRACT_INDEX.md" 2>/dev/null \
    | rg -o 'event_center_runtime_config_version:\s*[A-Za-z0-9._-]+' \
    | head -n1 \
    | sed -E 's/.*event_center_runtime_config_version:\s*//' \
    | xargs || true
}

extract_manifest_runtime_version_from_rev() {
  local rev="$1"
  git show "${rev}:contracts/versions/manifest.yaml" 2>/dev/null \
    | awk '
      /- name:\s*event_center_runtime_config_version/ {in_block=1; next}
      in_block && /value:/ {
        gsub(/"/, "", $2);
        print $2;
        exit
      }
      in_block && /^  - name:/ {in_block=0}
    ' \
    | head -n1 \
    | xargs || true
}

extract_py_runtime_version_from_rev() {
  local rev="$1"
  git show "${rev}:services/event_center_new/version.py" 2>/dev/null \
    | rg -o 'EVENT_CENTER_RUNTIME_CONFIG_VERSION\s*=\s*"[^"]+"' \
    | head -n1 \
    | sed -E 's/.*=\s*"([^"]+)"/\1/' \
    | xargs || true
}

extract_runtime_doc_version_from_rev() {
  local rev="$1"
  git show "${rev}:services/event_center_new/docs/runtime.md" 2>/dev/null \
    | rg -o 'runtime_config_version:\s*[A-Za-z0-9._-]+' \
    | head -n1 \
    | sed -E 's/.*runtime_config_version:\s*//' \
    | xargs || true
}

event_center_runtime_changed=0
base_idx_ver="$(extract_index_runtime_version_from_rev "${BASE_REF}")"
head_idx_ver="$(extract_index_runtime_version_from_rev "HEAD")"
if [[ -n "${base_idx_ver}" || -n "${head_idx_ver}" ]]; then
  if [[ "${base_idx_ver}" != "${head_idx_ver}" ]]; then
    event_center_runtime_changed=1
  fi
fi

base_manifest_ver="$(extract_manifest_runtime_version_from_rev "${BASE_REF}")"
head_manifest_ver="$(extract_manifest_runtime_version_from_rev "HEAD")"
if [[ -n "${base_manifest_ver}" || -n "${head_manifest_ver}" ]]; then
  if [[ "${base_manifest_ver}" != "${head_manifest_ver}" ]]; then
    event_center_runtime_changed=1
  fi
fi

base_py_ver="$(extract_py_runtime_version_from_rev "${BASE_REF}")"
head_py_ver="$(extract_py_runtime_version_from_rev "HEAD")"
if [[ -n "${base_py_ver}" || -n "${head_py_ver}" ]]; then
  if [[ "${base_py_ver}" != "${head_py_ver}" ]]; then
    event_center_runtime_changed=1
  fi
fi

base_doc_ver="$(extract_runtime_doc_version_from_rev "${BASE_REF}")"
head_doc_ver="$(extract_runtime_doc_version_from_rev "HEAD")"
if [[ -n "${base_doc_ver}" || -n "${head_doc_ver}" ]]; then
  if [[ "${base_doc_ver}" != "${head_doc_ver}" ]]; then
    event_center_runtime_changed=1
  fi
fi

if [[ -z "${schema_changed_services}" && "${event_center_runtime_changed}" -eq 0 ]]; then
  echo "[通过] 未检测到 schema 变更或 event_center runtime 版本锚点变更，无需执行四件套校验。"
  exit 0
fi

echo "[1/3] 检测变更触发器"
if [[ -n "${schema_changed_services}" ]]; then
  echo "  - schema_changed_services:"
  printf '%s\n' "${schema_changed_services}" | sed 's/^/    - /'
else
  echo "  - schema_changed_services: none"
fi
if [[ "${event_center_runtime_changed}" -eq 1 ]]; then
  echo "  - event_center_runtime_anchor_changed: yes"
else
  echo "  - event_center_runtime_anchor_changed: no"
fi

fail=0
if [[ -n "${schema_changed_services}" ]]; then
  echo "[2/3] 校验 schema 变更四件套"
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
else
  echo "[2/3] 未触发 schema 变更四件套。"
fi

echo "[3/3] 校验 event_center runtime 版本锚点四件套"
if [[ "${event_center_runtime_changed}" -eq 1 ]]; then
  missing=()
  check_changed_exact "docs/CONTRACT_INDEX.md" || missing+=("docs/CONTRACT_INDEX.md")
  check_changed_exact "contracts/versions/manifest.yaml" || missing+=("contracts/versions/manifest.yaml")
  check_changed_exact "services/event_center_new/version.py" || missing+=("services/event_center_new/version.py")
  check_changed_exact "services/event_center_new/docs/runtime.md" || missing+=("services/event_center_new/docs/runtime.md")
  check_changed_regex '^tools/local/check_event_center_.*guard.*\.sh$|^verification/.*/event_center_new/.*\.(py|sh|ya?ml)$|^verification/.*/contracts/test_contract_versions_manifest\.py$' || missing+=("guard_or_test(event_center_runtime_anchor)")

  if [[ ${#missing[@]} -gt 0 ]]; then
    echo "[失败] event_center_runtime_config_version 检测到变更，但四件套未齐全："
    printf '  - %s\n' "${missing[@]}"
    fail=1
  else
    echo "[通过] event_center runtime 版本锚点四件套齐全。"
  fi
else
  echo "[通过] 未触发 event_center runtime 版本锚点四件套。"
fi

if [[ "${fail}" -ne 0 ]]; then
  exit 1
fi

echo "[通过] 契约变更四件套守卫检查完成。"
