from __future__ import annotations

PIPELINE_MODE_QUICK_SNIPPETS: tuple[str, ...] = (
    "bash tools/local/verify_quick.sh --with-pipeline-mode-report",
    "bash tools/local/verify_quick.sh --with-pipeline-mode-report --with-agent-readyz",
)
