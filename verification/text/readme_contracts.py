from __future__ import annotations

README_CONTRACTS_VERSION = "readme-contracts-v1"

PIPELINE_MODE_QUICK_SNIPPETS: tuple[str, ...] = (
    "bash tools/local/verify_quick.sh --with-pipeline-mode-report",
    "bash tools/local/verify_quick.sh --with-pipeline-mode-report --with-agent-readyz",
)
