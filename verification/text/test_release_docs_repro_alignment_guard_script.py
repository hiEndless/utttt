from __future__ import annotations

import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

GUARD_SCRIPT = PROJECT_ROOT / "tools" / "local" / "check_release_docs_repro_alignment_guard.sh"

REPRO_BLOCK = """## x

release gate schema

```bash
git checkout -b tmp/release-gate-schema-repro
echo "// repro" >> verification/reports/release_gate_summary_v1.schema.json
bash tools/local/check_contract_change_bundle_guard.sh
```
"""


def _write_release_docs(root: Path, *, summary_include_last_line: bool = True) -> None:
    docs = root / "docs" / "operations"
    docs.mkdir(parents=True, exist_ok=True)
    latest = REPRO_BLOCK
    summary = REPRO_BLOCK if summary_include_last_line else REPRO_BLOCK.replace(
        "bash tools/local/check_contract_change_bundle_guard.sh\n", ""
    )
    handoff = REPRO_BLOCK
    (docs / "RELEASE_LATEST.md").write_text(latest, encoding="utf-8")
    (docs / "RELEASE_SUMMARY_20260312.md").write_text(summary, encoding="utf-8")
    (docs / "RELEASE_HANDOFF_20260312.md").write_text(handoff, encoding="utf-8")


def test_release_docs_repro_alignment_guard_passes(tmp_path: Path) -> None:
    _write_release_docs(tmp_path, summary_include_last_line=True)
    proc = subprocess.run(
        ["bash", str(GUARD_SCRIPT)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "对齐检查完成" in str(proc.stdout or "")


def test_release_docs_repro_alignment_guard_show_missing_outputs_debug(tmp_path: Path) -> None:
    _write_release_docs(tmp_path, summary_include_last_line=False)
    proc = subprocess.run(
        ["bash", str(GUARD_SCRIPT), "--show-missing"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    out = f"{proc.stdout}\n{proc.stderr}"
    assert "missing_line=bash tools/local/check_contract_change_bundle_guard.sh" in out
    assert "RELEASE_SUMMARY_20260312.md" in out
