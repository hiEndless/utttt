#!/usr/bin/env bash
set -euo pipefail

ENTRY="scripts/check_event_center_contract_guards.sh"
TOP_ENTRY="scripts/check_new_arch_guards.sh"
SHOW_LINKS="false"
MATCH_MODE="strict"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --show-links)
      SHOW_LINKS="true"
      shift
      ;;
    --strict)
      MATCH_MODE="strict"
      shift
      ;;
    --lenient)
      MATCH_MODE="lenient"
      shift
      ;;
    *)
      echo "[失败] 不支持的参数: $1"
      echo "用法: bash scripts/check_event_center_guard_wiring.sh [--show-links] [--strict|--lenient]"
      exit 1
      ;;
  esac
done

echo "[1/4] 检查 event_center 聚合入口存在"
if ! test -f "$ENTRY"; then
  echo "[失败] 缺少 $ENTRY"
  exit 1
fi
if ! test -f "$TOP_ENTRY"; then
  echo "[失败] 缺少 $TOP_ENTRY"
  exit 1
fi

echo "[2/4] 校验总入口引用 schema/runtime 聚合脚本"
if ! rg -q "check_event_center_contract_schema_guards\\.sh" "$ENTRY"; then
  echo "[失败] $ENTRY 未引用 check_event_center_contract_schema_guards.sh"
  exit 1
fi
if ! rg -q "check_event_center_runtime_family_guards\\.sh" "$ENTRY"; then
  echo "[失败] $ENTRY 未引用 check_event_center_runtime_family_guards.sh"
  exit 1
fi
if [[ "$SHOW_LINKS" == "true" ]]; then
  echo "[调试] $ENTRY 关键引用："
  rg -n "check_event_center_contract_schema_guards\\.sh|check_event_center_runtime_family_guards\\.sh|--quick" "$ENTRY"
fi

echo "[3/4] 校验总入口支持 quick 分支"
if ! rg -q -- "--quick" "$ENTRY"; then
  echo "[失败] $ENTRY 未声明 --quick"
  exit 1
fi
if [[ "$MATCH_MODE" == "strict" ]]; then
  if ! rg -q -- "check_event_center_contract_schema_guards\\.sh --quick" "$ENTRY"; then
    echo "[失败] $ENTRY quick 未调用 schema 聚合脚本（strict）"
    exit 1
  fi
  if ! rg -q -- "check_event_center_runtime_family_guards\\.sh --quick" "$ENTRY"; then
    echo "[失败] $ENTRY quick 未调用 runtime 聚合脚本（strict）"
    exit 1
  fi
else
  if ! rg -q -- "check_event_center_contract_schema_guards\\.sh" "$ENTRY"; then
    echo "[失败] $ENTRY quick 未出现 schema 聚合脚本（lenient）"
    exit 1
  fi
  if ! rg -q -- "check_event_center_runtime_family_guards\\.sh" "$ENTRY"; then
    echo "[失败] $ENTRY quick 未出现 runtime 聚合脚本（lenient）"
    exit 1
  fi
fi

echo "[4/4] 校验顶层入口已透传 event_center quick/only"
if ! rg -q -- "--event-center-quick" "$TOP_ENTRY"; then
  echo "[失败] $TOP_ENTRY 未声明 --event-center-quick"
  exit 1
fi
if [[ "$MATCH_MODE" == "strict" ]]; then
  if ! rg -q -- "check_event_center_contract_guards\\.sh --quick" "$TOP_ENTRY"; then
    echo "[失败] $TOP_ENTRY 未透传 event_center quick（strict）"
    exit 1
  fi
else
  if ! rg -q -- "check_event_center_contract_guards\\.sh" "$TOP_ENTRY"; then
    echo "[失败] $TOP_ENTRY 未出现 event_center 守卫入口（lenient）"
    exit 1
  fi
fi
if ! rg -q -- "--event-center-only" "$TOP_ENTRY"; then
  echo "[失败] $TOP_ENTRY 未声明 --event-center-only"
  exit 1
fi
if ! rg -q -- "check_event_center_contract_guards\\.sh$" "$TOP_ENTRY"; then
  echo "[失败] $TOP_ENTRY 未透传 event_center 全量"
  exit 1
fi
if [[ "$SHOW_LINKS" == "true" ]]; then
  echo "[调试] $TOP_ENTRY 关键引用："
  rg -n -- "--event-center-quick|--event-center-only|check_event_center_contract_guards\\.sh" "$TOP_ENTRY"
fi

echo "[通过] event_center 守卫接线检查完成。mode=$MATCH_MODE"
