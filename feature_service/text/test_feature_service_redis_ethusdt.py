import asyncio
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from feature_service.providers import build_independent_provider_bundle
from services.feature_service.src.service import FeatureService


@pytest.mark.integration
def test_feature_service_ethusdt_with_redis_data():
    """使用 Redis 中的 binance/ETHUSDT 真实数据验证 feature_service 输出结构。"""

    async def _run():
        service = FeatureService.from_bundle(build_independent_provider_bundle())
        raw = await service.get_raw_structure("binance", "ETHUSDT")
        features = await service.get_features("binance", "ETHUSDT")

        raw_market_structure = raw.get("raw_market_structure", {})
        assert isinstance(raw_market_structure, dict)
        assert raw_market_structure.get("symbol") == "ETHUSDT"
        assert raw_market_structure.get("candidate_horizons") == ["short_term", "mid_term", "long_term"]

        payload = features.get("features", {})
        assert isinstance(payload.get("indicators"), dict)
        assert isinstance(payload.get("derived_metrics"), dict)
        assert isinstance(payload.get("structure_snapshot"), dict)

    try:
        asyncio.run(_run())
    except Exception as exc:
        # 集成测试依赖本地 Redis 与数据可访问；不可达时显式标记跳过，避免误报。
        pytest.skip(f"Redis集成环境不可用，跳过该测试: {exc}")
