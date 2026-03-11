# Auditors Layer

Cross-service semantic/invariant auditors.

Current auditor:
- `semantic_contract_audit.py`
  - Input: `contracts/registry.yaml`, `contracts/semantic_policies/field_semantics.yaml`
  - Output: `verification/reports/semantic_audit.latest.json`
  - Error (fail): missing schema source; disallowed field location
  - Warning: expected shape mismatch; multi-shape drift on same field name

Run:
- `bash tools/local/audit_semantics.sh`
- strict mode: `bash tools/local/audit_semantics.sh --strict`
