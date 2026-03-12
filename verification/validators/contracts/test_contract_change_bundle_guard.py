from __future__ import annotations

import shutil
import stat
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SOURCE_GUARD = PROJECT_ROOT / "tools" / "local" / "check_contract_change_bundle_guard.sh"


def _run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), check=False, text=True, capture_output=True)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)

    _run(["git", "init", "-q"], cwd=repo)
    _run(["git", "config", "user.email", "ci@example.com"], cwd=repo)
    _run(["git", "config", "user.name", "CI"], cwd=repo)

    guard_path = repo / "tools" / "local" / "check_contract_change_bundle_guard.sh"
    guard_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_GUARD, guard_path)
    guard_path.chmod(guard_path.stat().st_mode | stat.S_IXUSR)

    _write(repo / "docs" / "CONTRACT_INDEX.md", "# index\n更新时间：2026-03-12\n")
    _write(
        repo / "contracts" / "versions" / "manifest.yaml",
        'version: 1\ncontract_versions:\n  - name: event_center_runtime_config_version\n    value: "event-center-runtime-v1"\n',
    )
    _write(
        repo / "services" / "event_center_new" / "version.py",
        'EVENT_CENTER_RUNTIME_CONFIG_VERSION = "event-center-runtime-v1"\n',
    )
    _write(
        repo / "services" / "event_center_new" / "docs" / "runtime.md",
        "- `runtime_config_version: event-center-runtime-v1`\n",
    )

    _run(["git", "add", "."], cwd=repo)
    _run(["git", "commit", "-m", "base", "--quiet"], cwd=repo)
    return repo


def test_guard_fails_when_runtime_anchor_changes_without_bundle(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)

    _write(
        repo / "services" / "event_center_new" / "version.py",
        'EVENT_CENTER_RUNTIME_CONFIG_VERSION = "event-center-runtime-v2"\n',
    )
    _run(["git", "add", "services/event_center_new/version.py"], cwd=repo)
    _run(["git", "commit", "-m", "bump runtime version only", "--quiet"], cwd=repo)

    proc = _run(
        ["bash", "tools/local/check_contract_change_bundle_guard.sh"],
        cwd=repo,
    )

    assert proc.returncode != 0
    out = f"{proc.stdout}\n{proc.stderr}"
    assert "event_center_runtime_config_version 检测到变更" in out
    assert "docs/CONTRACT_INDEX.md" in out
    assert "contracts/versions/manifest.yaml" in out
    assert "services/event_center_new/docs/runtime.md" in out


def test_guard_passes_when_runtime_anchor_bundle_is_complete(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)

    _write(
        repo / "services" / "event_center_new" / "version.py",
        'EVENT_CENTER_RUNTIME_CONFIG_VERSION = "event-center-runtime-v2"\n',
    )
    _write(
        repo / "services" / "event_center_new" / "docs" / "runtime.md",
        "- `runtime_config_version: event-center-runtime-v2`\n",
    )
    _write(
        repo / "contracts" / "versions" / "manifest.yaml",
        'version: 1\ncontract_versions:\n  - name: event_center_runtime_config_version\n    value: "event-center-runtime-v2"\n',
    )
    _write(
        repo / "docs" / "CONTRACT_INDEX.md",
        "# index\n更新时间：2026-03-12\n- `event_center_runtime_config_version: event-center-runtime-v2`\n",
    )
    _write(
        repo / "verification" / "validators" / "contracts" / "test_contract_versions_manifest.py",
        "def test_manifest_placeholder():\n    assert True\n",
    )

    _run(["git", "add", "."], cwd=repo)
    _run(["git", "commit", "-m", "bump runtime version with bundle", "--quiet"], cwd=repo)

    proc = _run(
        ["bash", "tools/local/check_contract_change_bundle_guard.sh"],
        cwd=repo,
    )

    assert proc.returncode == 0
    assert "event_center runtime 版本锚点四件套齐全" in proc.stdout

