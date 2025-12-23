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
    # 检查是否是多时间维度数据
    if isinstance(event, dict) and "analysis_by_timeframe" in event:
        # 多时间维度数据，直接传递给 orchestrator
        mode = "default"  # 多时间维度使用默认模式
        from agent_server.agents.experts import load_expert, load_card
        factory = TeamFactory(lambda name: load_expert(name), lambda name: load_card(name))
        team = factory.build(template=mode)
        orchestrator = TeamOrchestrator()
        query = json.dumps(event, ensure_ascii=False) if isinstance(event, dict) else str(event)
        return await orchestrator.run(mode, team, query)
    
    # 单事件分析（原有逻辑）
    mode, _ = route_event(event)
    from agent_server.agents.experts import load_expert, load_card
    factory = TeamFactory(lambda name: load_expert(name), lambda name: load_card(name))
    team = factory.build(template=mode)
    orchestrator = TeamOrchestrator()
    # 将 payload 转换为 JSON 字符串，而不是使用 str()
    query = json.dumps(event.payload, ensure_ascii=False) if isinstance(event.payload, dict) else str(event.payload)
    return await orchestrator.run(mode, team, query)