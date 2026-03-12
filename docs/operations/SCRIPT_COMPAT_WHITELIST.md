# Script Compatibility Whitelist

## Purpose

This document records the compatibility whitelist lifecycle during directory refactor.
As of 2026-03-12, legacy `scripts/*` compatibility wrappers have been fully retired.

Canonical machine-readable source:
- `verification/guards/script_compat_whitelist.yaml`

Validation command:
- `bash tools/local/check_script_compat_whitelist.sh`
- included in regression/nightly CI path:
  - `bash tools/ci/verify_regression.sh`
  - `bash tools/ci/verify_nightly.sh`

## Current Boundary

1. Workflow-pinned scripts
- None.

2. Snapshot/help-pinned scripts
- None.

3. Text-wiring-pinned scripts
- None.

4. Compatibility wrappers
- None.

## Exit Criteria

1. Replace workflow references with `tools/ci/*` paths and update workflow guards.
2. Move snapshot guards to inspect `tools/*` entrypoints (then refresh snapshots).
3. Replace text-scanning guards with semantic checks (AST/command intent) or retarget to `tools/*` files.
4. Completed: `scripts/*` compatibility wrappers removed.

Detailed plan:
- `docs/operations/SCRIPT_HARD_PINNED_DECOMMISSION_PLAN.md`
