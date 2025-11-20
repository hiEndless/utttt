from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
)
from agent_server.configs.source import get_agent_config
import json
from pathlib import Path


def get_agent_card(name: str) -> AgentCard:
    cfg = _load_card_config(name)
    if not cfg:
        raise ValueError(f"agent card config not found: {name}")
    return _card_from_config(name, cfg)

def _load_agent_url(name: str, default_url: str) -> str:
    cfg = get_agent_config(name)
    url = cfg.get("a2a_url")
    return url or default_url


def _load_card_config(name: str) -> dict | None:
    base = Path(__file__).resolve().parent.parent / "configs" / "cards"
    path = base / f"{name}.json"
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _card_from_config(name: str, cfg: dict) -> AgentCard:
    url_override = _load_agent_url(name, cfg.get("url") or "")
    caps = cfg.get("capabilities") or {}
    skills_cfg = cfg.get("skills") or []
    skills = [
        AgentSkill(
            id=s.get("id"),
            name=s.get("name"),
            description=s.get("description"),
            tags=s.get("tags") or [],
            examples=s.get("examples") or [],
        )
        for s in skills_cfg
    ]
    return AgentCard(
        name=cfg.get("name") or name,
        description=cfg.get("description") or "",
        url=url_override,
        version=cfg.get("version") or "1.0.0",
        defaultInputModes=cfg.get("defaultInputModes") or ["text", "text/plain"],
        defaultOutputModes=cfg.get("defaultOutputModes") or ["text", "text/plain"],
        capabilities=AgentCapabilities(
            streaming=bool(caps.get("streaming", True)),
            pushNotifications=bool(caps.get("pushNotifications", False)),
            stateTransitionHistory=bool(caps.get("stateTransitionHistory", False)),
        ),
        authentication={"schemes": ["public"]},
        skills=skills,
    )