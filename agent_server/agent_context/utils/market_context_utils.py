"""
市场环境感知工具函数
用于根据市场环境动态调整风控参数
"""
from typing import Dict, Any


def adjust_risk_by_market_context(market_state: Dict[str, Any]) -> Dict[str, float]:
    """
    根据市场环境动态调整风控参数
    
    Args:
        market_state: 市场状态信息，包含波动率、趋势等
        
    Returns:
        风控调整参数，包含风险乘数和Z-Score放松系数
    """
    if not market_state:
        return {"crowd_risk_multiplier": 1.0, "zscore_relaxation": 0.0}
    
    # 获取市场状态关键指标
    vol_regime = market_state.get("short_term", {}).get("risk", "normal")
    market_direction = market_state.get("long_term", {}).get("direction", "neutral")
    short_term_direction = market_state.get("short_term", {}).get("direction", "neutral")
    
    # 基础调整参数
    crowd_risk_multiplier = 1.0
    zscore_relaxation = 0.0
    
    # 根据波动率制度调整
    if vol_regime == "low":
        # 低波动环境，放宽风控要求
        crowd_risk_multiplier = 0.7
        zscore_relaxation = 0.3
    elif vol_regime == "high":
        # 高波动环境，适度收紧风控
        crowd_risk_multiplier = 1.2
        zscore_relaxation = -0.1
    elif vol_regime == "extreme":
        # 极端波动环境，严格风控
        crowd_risk_multiplier = 1.5
        zscore_relaxation = -0.2
    
    # 根据市场趋势方向调整（主要针对主流币）
    if market_direction == "bullish" and short_term_direction == "bullish":
        # 牛市环境，对多头仓位更加宽容
        crowd_risk_multiplier = round(crowd_risk_multiplier * 0.8, 2)
        zscore_relaxation = round(zscore_relaxation + 0.2, 2)
    elif market_direction == "bearish" and short_term_direction == "bearish":
        # 熊市环境，对空头仓位更加宽容
        crowd_risk_multiplier = round(crowd_risk_multiplier * 0.8, 2)
        zscore_relaxation = round(zscore_relaxation + 0.2, 2)
    
    return {
        "crowd_risk_multiplier": max(0.5, min(2.0, crowd_risk_multiplier)),  # 限制在合理范围内
        "zscore_relaxation": max(-0.5, min(0.5, zscore_relaxation))
    }


def is_favorable_market_condition(market_state: Dict[str, Any]) -> bool:
    """
    判断当前市场条件是否有利于放宽风控要求
    
    Args:
        market_state: 市场状态信息
        
    Returns:
        是否适合放宽风控
    """
    if not market_state:
        return False
    
    vol_regime = market_state.get("short_term", {}).get("risk", "normal")
    market_direction = market_state.get("long_term", {}).get("direction", "neutral")
    short_term_direction = market_state.get("short_term", {}).get("direction", "neutral")
    
    # 低波动且趋势一致的市场环境适合放宽风控
    if vol_regime == "low" and market_direction == short_term_direction:
        return True
    
    return False