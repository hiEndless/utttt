from typing import Dict, List, Any, Callable

from agent_server.config import TEAM_TEMPLATES


class TeamFactory:
    def __init__(self, load_agent: Callable[[str], Any], load_card: Callable[[str], Any] | None = None):
        self._load_agent = load_agent
        self._load_card = load_card

    def build(self, template: str) -> List:
        names: List[str] = TEAM_TEMPLATES.get(template, TEAM_TEMPLATES["default"])
        if self._load_card:
            return [{"agent": self._load_agent(n), "card": self._load_card(n), "name": n} for n in names]
        return [self._load_agent(n) for n in names]