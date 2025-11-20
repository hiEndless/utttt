from typing import Dict

from agent_server.events import EventSignal, route_event
from agent_server.teams import TeamFactory, TeamOrchestrator


async def handle_event(event: EventSignal) -> Dict:
    mode, _ = route_event(event)
    from agent_server.agents.experts import load_expert, load_card
    factory = TeamFactory(lambda name: load_expert(name), lambda name: load_card(name))
    team = factory.build(template=mode)
    orchestrator = TeamOrchestrator()
    return await orchestrator.run(mode, team, str(event.payload))