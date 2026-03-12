# Script Compatibility Whitelist

## Purpose

During directory refactor, some `scripts/*` files cannot be removed or renamed yet,
because they are still hard-pinned by workflows, snapshot guards, or text-wiring guards.

Canonical machine-readable source:
- `verification/guards/script_compat_whitelist.yaml`

Validation command:
- `bash tools/local/check_script_compat_whitelist.sh`
- included in regression/nightly CI path:
  - `bash tools/ci/verify_regression.sh`
  - `bash tools/ci/verify_nightly.sh`

## Current Boundary

1. Workflow-pinned scripts
- Trigger path or workflow job hard references require keeping script path stable.

2. Snapshot/help-pinned scripts
- `--help` output snapshots and keyline snapshots bind exact script entrypoint behavior.

3. Text-wiring-pinned scripts
- Some guards parse script source text for specific wiring lines, so pure wrapper replacement may break guards.

4. Compatibility wrappers
- Several scripts are now thin wrappers to `tools/local/*`; they are retained during compatibility window.

## Exit Criteria

1. Replace workflow references with `tools/ci/*` paths and update workflow guards.
2. Move snapshot guards to inspect `tools/*` entrypoints (then refresh snapshots).
3. Replace text-scanning guards with semantic checks (AST/command intent) or retarget to `tools/*` files.
4. After one stable iteration window, remove `scripts/*` compatibility wrappers in batches.

Detailed plan:
- `docs/operations/SCRIPT_HARD_PINNED_DECOMMISSION_PLAN.md`
