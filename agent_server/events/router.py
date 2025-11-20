from typing import Tuple

from agent_server.config import EVENT_TEAM_MAP
from agent_server.events.models import EventSignal


def route_event(event: EventSignal) -> Tuple[str, str]:
    mapping = EVENT_TEAM_MAP.get(event.type)
    if not mapping:
        return "default", "default"
    mode = mapping.get(event.strength, "default")
    return mode, event.type