# 未来数据源骨架（news/social/onchain）

## 路径

- canonical：`services/feature_service/src/providers/future_source_providers.py` 与 `services/feature_service/src/ports/{news_provider,social_provider,onchain_provider}.py`
- 兼容壳：已在 Batch B 下线（providers）与 Batch A 下线（ports）


## 当前状态

已新增预留骨架，但尚未接入 `FeatureService` 主输出链路。

新增接口：

- `services/feature_service/src/ports/news_provider.py`
- `services/feature_service/src/ports/social_provider.py`
- `services/feature_service/src/ports/onchain_provider.py`

新增 provider 占位：

- `services/feature_service/src/providers/future_source_providers.py`
  - `Noop*Provider`
  - `Static*Provider`
  - `Fallback*Provider`
  - `Unavailable*Provider`

统一最小返回结构（已落地）：

```json
{
  "source_type": "news|social|onchain",
  "available": false,
  "provider_state": "primary|fallback|static|noop|unavailable|empty",
  "as_of_ms": null,
  "features": {}
}
```

- 目的：即使未来数据源暂未接入主链路，也保证 provider 输出字段稳定，避免空字典导致语义漂移。

## 作用

- 为未来新闻/社交/链上特征接入提供统一接口形态。
- 复用当前服务的降级语义（`mark_degraded`），保证扩展后可观测性一致。

## 未接入部分

- 当前 `service.py` 未消费上述 provider。
- `/features` 暂未输出 `news/social/onchain` 特征字段。

## 建议接入顺序

1. 在 `ports` 和 `ProviderBundle` 定义三类 provider 注入位。
2. 在 `FeatureService.get_features` 增加可选输出块（建议 `features.alternative_sources`）。
3. 在 `contracts.py` 增加对应类型约束并补契约测试。
4. 在 `normalizers` 增加 source 级标准化规则（`source/timestamp/confidence/freshness/degraded`）。
