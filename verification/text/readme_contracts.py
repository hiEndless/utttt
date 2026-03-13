from __future__ import annotations

# README 契约版本演进记录：
# - readme-contracts-v1：初始引入，约束 pipeline_mode quick 单命令与联合观测命令。
# - readme-contracts-v2：增加 CLI_HELP_SNAPSHOT 版本锚点与 docs_bundle 日志版本输出联动。
README_CONTRACTS_VERSION = "readme-contracts-v2"

PIPELINE_MODE_QUICK_SNIPPETS: tuple[str, ...] = (
    "bash tools/local/verify_quick.sh --with-pipeline-mode-report",
    "bash tools/local/verify_quick.sh --with-pipeline-mode-report --with-agent-readyz",
)
