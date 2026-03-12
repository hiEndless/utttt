from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from services.feature_service.src.version import FEATURE_RESPONSE_SCHEMA_VERSION

SCHEMA_VERSION = FEATURE_RESPONSE_SCHEMA_VERSION


class ResponseMeta(BaseModel):
    # 统一版本字段，便于下游做兼容分流。
    schema_version: str = Field(default=SCHEMA_VERSION)
    generated_at_ms: int
    degraded: bool = False
    degraded_reasons: List[str] = Field(default_factory=list)


class RawMarketStructureModel(BaseModel):
    # 关键结构字段强类型化，附加字段仍通过 dict 容器承载。
    symbol: str
    candidate_horizons: List[str] = Field(default_factory=list)
    pre_decision_structure: Dict[str, Any] = Field(default_factory=dict)
    horizons: Dict[str, Any] = Field(default_factory=dict)
    orderbook: Dict[str, Any] = Field(default_factory=dict)
    open_interest: Dict[str, Any] = Field(default_factory=dict)
    behavioral: Dict[str, Any] = Field(default_factory=dict)


class DerivedMetricsModel(BaseModel):
    candidate_horizons: List[str] = Field(default_factory=list)
    indicator_metrics: Dict[str, Any] = Field(default_factory=dict)
    horizon_metrics: Dict[str, Any] = Field(default_factory=dict)
    orderbook_metrics: Dict[str, Any] = Field(default_factory=dict)
    open_interest_metrics: Dict[str, Any] = Field(default_factory=dict)
    behavior_metrics: Dict[str, Any] = Field(default_factory=dict)
    pre_decision_metrics: Dict[str, Any] = Field(default_factory=dict)


class StructureSnapshotModel(BaseModel):
    pre_decision_structure: Dict[str, Any] = Field(default_factory=dict)
    horizons: Dict[str, Any] = Field(default_factory=dict)


class AlternativeSourceEntryModel(BaseModel):
    source_type: str
    available: bool
    provider_state: str
    data_source: str
    inference_source: str
    as_of_ms: Any = None
    features: Dict[str, Any] = Field(default_factory=dict)


class FeatureSnapshot(BaseModel):
    exchange: str
    symbol: str
    indicators: Dict[str, Any] = Field(default_factory=dict)
    derived_metrics: DerivedMetricsModel = Field(default_factory=DerivedMetricsModel)
    structure_snapshot: StructureSnapshotModel = Field(default_factory=StructureSnapshotModel)
    alternative_sources: Dict[str, AlternativeSourceEntryModel] = Field(default_factory=dict)


class RawStructureSnapshot(BaseModel):
    exchange: str
    symbol: str
    raw_market_structure: RawMarketStructureModel


class RawStructureResponse(BaseModel):
    meta: ResponseMeta
    data: RawStructureSnapshot


class FeatureResponse(BaseModel):
    meta: ResponseMeta
    data: FeatureSnapshot
