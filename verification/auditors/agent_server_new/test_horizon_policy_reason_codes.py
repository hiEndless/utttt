from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.domain.horizon_policy_reasons import (
    HORIZON_POLICY_REASON_BLOCKED_GENERIC,
    HORIZON_POLICY_REASON_CODES,
    HORIZON_POLICY_REASON_POLICY_REASON_PREFIX,
    HORIZON_POLICY_REASON_REDUCE_RISK,
    HORIZON_POLICY_REASON_WAIT_CONFIRMATION,
    horizon_policy_reason_code,
    horizon_policy_reason_tag,
)


def test_horizon_policy_reason_codes_registry_is_unique() -> None:
    assert len(HORIZON_POLICY_REASON_CODES) == len(set(HORIZON_POLICY_REASON_CODES))


def test_horizon_policy_reason_code_mapping() -> None:
    assert horizon_policy_reason_code("wait_confirmation") == HORIZON_POLICY_REASON_WAIT_CONFIRMATION
    assert horizon_policy_reason_code("reduce_risk") == HORIZON_POLICY_REASON_REDUCE_RISK
    assert horizon_policy_reason_code("custom_policy") == HORIZON_POLICY_REASON_BLOCKED_GENERIC


def test_horizon_policy_reason_tag_has_canonical_prefix() -> None:
    out = horizon_policy_reason_tag("timeframe_mixed")
    assert out == f"{HORIZON_POLICY_REASON_POLICY_REASON_PREFIX}timeframe_mixed"

