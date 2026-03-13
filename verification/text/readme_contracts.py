from __future__ import annotations

from pathlib import Path

# 版本升级注意：
# 升级 README_CONTRACTS_VERSION 时，必须同步更新：
# 1) verification/text/readme_contracts_version.baseline
# 2) docs/operations/CLI_HELP_SNAPSHOT.md 的版本锚点
# README 契约版本演进记录：
# - readme-contracts-v1：初始引入，约束 pipeline_mode quick 单命令与联合观测命令。
# - readme-contracts-v2：增加 CLI_HELP_SNAPSHOT 版本锚点与 docs_bundle 日志版本输出联动。
README_CONTRACTS_VERSION = "readme-contracts-v2"
README_CONTRACTS_BASELINE_PATH = Path("verification/text/readme_contracts_version.baseline")
README_CONTRACTS_DOC_ANCHOR = f"README_CONTRACTS_VERSION={README_CONTRACTS_VERSION}"
README_CONTRACTS_SNIPPETS_DOCS: tuple[Path, ...] = tuple(
    sorted(
        (
            Path("services/agent_server_new/README.md"),
            Path("verification/reports/README.md"),
        ),
        key=lambda p: str(p),
    )
)
README_CONTRACTS_DOC_LABELS: dict[Path, str] = {
    Path("services/agent_server_new/README.md"): "agent_server_new_readme",
    Path("verification/reports/README.md"): "verification_reports_readme",
}

PIPELINE_MODE_QUICK_SNIPPETS: tuple[str, ...] = tuple(
    sorted(
        (
            "bash tools/local/verify_quick.sh --with-pipeline-mode-report",
            "bash tools/local/verify_quick.sh --with-pipeline-mode-report --with-agent-readyz",
        )
    )
)

README_CONTRACTS_DOCS_REQUIRED_SNIPPETS: dict[Path, tuple[str, ...]] = dict(
    sorted(
        {
            Path("services/agent_server_new/README.md"): PIPELINE_MODE_QUICK_SNIPPETS + ("pipeline_mode_summary",),
            Path("verification/reports/README.md"): PIPELINE_MODE_QUICK_SNIPPETS,
        }.items(),
        key=lambda kv: str(kv[0]),
    )
)


def get_required_snippets_for_doc(path: Path) -> tuple[str, ...]:
    return tuple(README_CONTRACTS_DOCS_REQUIRED_SNIPPETS.get(Path(path), ()))
