# Contracts Layer

Cross-service contract single-source governance layer.

Subdirs:
- `schemas/`: schema registry and schema source mapping
- `mappings/`: schema-code mapping registry
- `semantic_policies/`: semantic constraints and lifecycle policies
- `versions/`: version manifests and compatibility matrix

Compatibility note:
- Runtime schema files still live in service-local `*/docs/*.schema.json` during this phase.
- This layer provides canonical registries and migration metadata.
