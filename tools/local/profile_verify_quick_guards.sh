#!/usr/bin/env bash
set -euo pipefail

REPORT_JSON="${1:-verification/reports/verify_quick_timing.latest.json}"
REPORT_MD="${2:-docs/operations/VERIFY_QUICK_TIMING_BASELINE.md}"

now_ms() {
  python3 - <<'PY'
import time
print(int(time.time() * 1000))
PY
}

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

STEPS=(
  "check_structure|bash tools/local/check_structure.sh"
  "check_script_compat_whitelist|bash tools/local/check_script_compat_whitelist.sh"
  "check_docs_contracts_bundle|bash tools/local/check_docs_contracts_bundle.sh"
  "check_source_semantics_guard|bash tools/local/check_source_semantics_guard.sh"
  "verify_all_quick|bash tools/ci/verify_all.sh --quick"
  "sync_contract_indexes|bash tools/local/sync_contract_indexes.sh"
  "audit_semantics|bash tools/local/audit_semantics.sh"
  "check_semantic_critical_warning_guard|bash tools/local/check_semantic_critical_warning_guard.sh"
)

mkdir -p "$(dirname "$REPORT_JSON")" "$(dirname "$REPORT_MD")"

overall_start="$(now_ms)"
step_rows_json=""
step_rows_md=""
total_duration=0

for pair in "${STEPS[@]}"; do
  name="${pair%%|*}"
  cmd="${pair#*|}"
  echo "[profile] running: $name"
  start="$(now_ms)"
  if eval "$cmd"; then
    status="passed"
  else
    status="failed"
  fi
  end="$(now_ms)"
  duration="$((end - start))"
  total_duration="$((total_duration + duration))"
  step_rows_md="${step_rows_md}| \`${name}\` | \`${status}\` | ${duration} |\n"
  if [[ -n "$step_rows_json" ]]; then
    step_rows_json="${step_rows_json},"
  fi
  step_rows_json="${step_rows_json}{\"name\":\"${name}\",\"status\":\"${status}\",\"duration_ms\":${duration}}"
  if [[ "$status" != "passed" ]]; then
    break
  fi
done

overall_end="$(now_ms)"
wall_duration="$((overall_end - overall_start))"

python3 - <<PY
import json
from pathlib import Path

report = {
    "schema_version": "verify_quick_timing_v1",
    "generated_at_ms": ${overall_end},
    "total_duration_ms": ${total_duration},
    "wall_duration_ms": ${wall_duration},
    "steps": [${step_rows_json}],
}
Path("${REPORT_JSON}").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

cat > "$REPORT_MD" <<EOF
# Verify Quick Timing Baseline

更新时间：$(date +%F)
来源：\`tools/local/profile_verify_quick_guards.sh\`
JSON 报告：\`${REPORT_JSON}\`

## 汇总

- 累计步骤耗时：\`${total_duration} ms\`
- 墙钟耗时：\`${wall_duration} ms\`

## 逐步耗时

| Step | Status | Duration (ms) |
|---|---|---:|
$(printf "%b" "$step_rows_md")

## 说明

- 该基线用于观察 \`verify_quick\` 外层编排变化后的趋势。
- 如需刷新，执行：
\`\`\`bash
bash tools/local/profile_verify_quick_guards.sh
\`\`\`
EOF

echo "[ok] wrote ${REPORT_JSON}"
echo "[ok] wrote ${REPORT_MD}"
