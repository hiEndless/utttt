import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def test_legacy_pipeline_default_guard_bootstrap_default_false() -> None:
    path = Path(PROJECT_ROOT) / "services" / "agent_server_new" / "app" / "bootstrap.py"
    text = path.read_text(encoding="utf-8")
    assert 'AGENT_LEGACY_PIPELINE_ENABLED", "false"' in text


def test_legacy_pipeline_default_guard_readme_has_migration_notice() -> None:
    path = Path(PROJECT_ROOT) / "services" / "agent_server_new" / "README.md"
    text = path.read_text(encoding="utf-8")
    assert "迁移兼容开关" in text
    assert "常态环境保持 `false`" in text
