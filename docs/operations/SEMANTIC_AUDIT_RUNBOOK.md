# Semantic Audit Runbook

## Purpose

Audit cross-service contract semantics drift using:

- `contracts/registry.yaml`
- `contracts/semantic_policies/field_semantics.yaml`

## Commands

1. Sync contract indexes:

```bash
bash tools/local/sync_contract_indexes.sh
```

2. Run semantic audit (non-strict):

```bash
bash tools/local/audit_semantics.sh
```

3. Run strict mode (warnings fail):

```bash
bash tools/local/audit_semantics.sh --strict
```

## Output

- report: `verification/reports/semantic_audit.latest.json`
- exit code:
  - `0`: no error (warnings allowed in non-strict)
  - `1`: semantic hard errors (missing source/disallowed location)
  - `2`: strict mode warning failure

## Current policy boundary

Hard-fail checks:
- schema source must exist
- `allowed_locations` must not drift

Warning checks:
- `expected_shape` mismatch
- same field name appears with multiple shapes
