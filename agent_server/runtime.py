from typing import Dict
import json

from agent_server.events import EventSignal, route_event
from agent_server.teams import TeamFactory, TeamOrchestrator


async def handle_event(event: EventSignal) -> Dict:
    """
    处理事件（支持单事件和多时间维度数据）
    
    Args:
        event: EventSignal 或包含多时间维度数据的字典
    """
    # 检查是否是多时间维度数据（支持两种格式：analysis_by_timeframe 和 indicators_by_timeframe）
    if isinstance(event, dict) and ("analysis_by_timeframe" in event or "indicators_by_timeframe" in event):
        # 多时间维度数据，直接传递给 orchestrator
        mode = "default"  # 多时间维度使用默认模式
        from agent_server.agents.experts import load_expert, load_card
        factory = TeamFactory(lambda name: load_expert(name), lambda name: load_card(name))
        team = factory.build(template=mode)
        orchestrator = TeamOrchestrator()
        query = json.dumps(event, ensure_ascii=False) if isinstance(event, dict) else str(event)
        return await orchestrator.run(mode, team, query)
    
    # 单事件分析（原有逻辑）
    # 如果传入的是字典但不是多时间维度数据，需要先转换为 EventSignal
    if isinstance(event, dict):
        # 尝试从字典创建 EventSignal
        from agent_server.events.models import EventSignal
        event_type = event.get("event_type", "market_signal")
        event_level = event.get("event_level", "1")
        level = int(event_level) if isinstance(event_level, (int, str)) and str(event_level).isdigit() else 1
        if level >= 4:
            strength = "high"
        elif level >= 3:
            strength = "medium"
        else:
            strength = "low"
        
        # 根据事件类型确定信号类型
        if "force_" in event_type or "spike" in event_type:
            signal_type = "market_spike"
        elif "combo" in event_type:
            signal_type = "market_signal"
        elif "price" in event_type or "depth" in event_type:
            signal_type = "market_spike"
        else:
            signal_type = "market_signal"
        
        event = EventSignal(
            type=signal_type,
            payload=event,
            strength=strength
        )
    
    mode, _ = route_event(event)
    from agent_server.agents.experts import load_expert, load_card
    factory = TeamFactory(lambda name: load_expert(name), lambda name: load_card(name))
    team = factory.build(template=mode)
    orchestrator = TeamOrchestrator()
    # 将 payload 转换为 JSON 字符串，而不是使用 str()
    query = json.dumps(event.payload, ensure_ascii=False) if isinstance(event.payload, dict) else str(event.payload)
    return await orchestrator.run(mode, team, query)