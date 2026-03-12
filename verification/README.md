# Verification Layer

This directory is the phase-1 scaffold for non-business validation capabilities.

Subdirs:
- `guards/`: contract and compatibility guard wrappers
- `auditors/`: cross-workflow invariant auditors
- `replay/`: replay and diff tools
- `validators/`: reusable schema/contract validators
- `reports/`: machine-readable verification outputs

Entry points:
- `bash verification/run_suite.sh --suite=new_arch_full`
- `bash verification/run_suite.sh --suite=quick`
- `bash tools/ci/verify_all.sh`
- `python3 -m verification.replay.replay_event_center --help`
- `python3 -m verification.auditors.semantic_contract_audit --help`

Report output:
- `bash verification/run_suite.sh --suite=quick --report-json=verification/reports/quick.latest.json`
- report schema: `verification/reports/verification_report.schema.json`

Migration map:
- `verification/migration_map.yaml`

Current strategy:
- Existing production checks remain under `scripts/check_*`.
- `verification/guards/*.sh` are compatibility wrappers for phased extraction.
- CI can migrate to verification entrypoints without breaking existing checks.
- Shared validator extraction started: `verification/validators/local_refs_schema.py` (keeps legacy import compatibility via `verification/validators/execution_service/schema_utils.py`).
