# Verification Layer

This directory is the phase-1 scaffold for non-business validation capabilities.

Subdirs:
- `guards/`: contract and compatibility guards
- `auditors/`: cross-workflow invariant auditors
- `replay/`: replay and diff tools
- `validators/`: reusable schema/contract validators
- `reports/`: machine-readable verification outputs

Current status:
- Existing production guard scripts remain under `scripts/`.
- `verification/suites.yaml` is the initial suite registry.
