# Semantic Policies

This directory stores machine-readable semantic constraints for cross-service contracts.

Phase-1 scope:
- Document stable semantic meanings for reused fields.
- Define deprecation lifecycle rules.
- Keep policy files small and executable by future semantic checkers.

Current policy files:
- `field_semantics.yaml`
- `deprecation_policy.yaml`
- `source_semantics.yaml`

Runtime helper:
- `source_semantics.py`：为业务服务提供统一读取入口（如 alternative source 的 `provider_state` 枚举与 unavailable 状态集合）。
