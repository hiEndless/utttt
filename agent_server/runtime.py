from typing import Dict
import json

from agent_server.events import EventSignal, route_event
from agent_server.teams import TeamFactory, TeamOrchestrator


async def handle_event(event: EventSignal) -> Dict:
    mode, _ = route_event(event)
    from agent_server.agents.experts import load_expert, load_card
    factory = TeamFactory(lambda name: load_expert(name), lambda name: load_card(name))
    team = factory.build(template=mode)
    orchestrator = TeamOrchestrator()
    # 将 payload 转换为 JSON 字符串，而不是使用 str()
    query = json.dumps(event.payload, ensure_ascii=False) if isinstance(event.payload, dict) else str(event.payload)
    return await orchestrator.run(mode, team, query)