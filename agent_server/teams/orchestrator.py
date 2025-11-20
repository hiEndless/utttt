from typing import List, Dict

from agent_server.communication import A2ACommunicator
from agent_server.communication.a2a import A2ASession
from agent_server.config import SCORING_WEIGHTS, PIPELINE_OPTIONS
from agent_server.teams.scoring import auto_score
from agent_server.a2a.cards import get_agent_card


class Debate:
    def __init__(self):
        self.c = A2ACommunicator()

    async def run(self, prompts: List[str]) -> List[str]:
        return await self.c.debate(prompts)


class Delphi:
    def __init__(self):
        self.c = A2ACommunicator()

    async def run(self, prompts: List[str]) -> List[str]:
        return await self.c.delphi(prompts)


class NVariant:
    def __init__(self):
        self.c = A2ACommunicator()

    async def run(self, prompts: List[str]) -> List[str]:
        return await self.c.n_variant(prompts)


class TeamOrchestrator:
    def __init__(self):
        self.session = A2ASession()

    async def run(self, mode: str, agents: List, query: str) -> Dict:
        if not agents or not isinstance(agents[0], dict):
            raise RuntimeError("Agents must be provided with cards for A2A communication")
        names = [a.get("name") or getattr(a["agent"], "name", "agent") for a in agents]
        prompts = await self.session.broadcast(agents, query)
        if mode == "debate":
            outputs = await Debate().run(prompts)
        elif mode == "delphi":
            outputs = await Delphi().run(prompts)
        elif mode == "n_variant":
            outputs = await NVariant().run(prompts)
        else:
            outputs = prompts
        import json
        scores = auto_score(outputs)
        outputs_scored: List[str] = []
        for i, t in enumerate(outputs):
            s = scores.get(i, 0.0)
            try:
                obj = json.loads(t)
                m = obj.get("metrics") or {}
                m["auto_score"] = s
                obj["metrics"] = m
                outputs_scored.append(json.dumps(obj, ensure_ascii=False))
            except Exception:
                obj = {
                    "agent": names[i] if i < len(names) else f"agent-{i}",
                    "task": "analysis",
                    "content": {"summary": (t or "")[:160], "details": t or ""},
                    "confidence": 0.0,
                    "rationale": "",
                    "metrics": {"auto_score": s},
                    "sources": [],
                    "tool_calls": [],
                    "timestamp": "",
                }
                outputs_scored.append(json.dumps(obj, ensure_ascii=False))
        outputs = outputs_scored
        from a2a.client import ClientFactory, ClientConfig
        from a2a.types import Message, Part, TextPart, Role, TransportProtocol
        options = PIPELINE_OPTIONS.get(mode, {"reflection": True, "fusion": True})
        refl_card = get_agent_card("reflection")
        config = ClientConfig(streaming=False, supported_transports=[TransportProtocol.jsonrpc], use_client_preference=False)
        factory = ClientFactory(config)
        refl_payload = json.dumps({"names": names, "outputs": outputs, "mode": mode}, ensure_ascii=False)
        if options.get("reflection", False):
            try:
                refl_client = factory.create(refl_card)
                reflection = None
                async for event in refl_client.send_message(Message(role=Role.user, parts=[Part(root=TextPart(text=refl_payload))])):
                    if hasattr(event, "parts"):
                        from a2a.utils import get_message_text
                        reflection = get_message_text(event)
                        break
                    break
                try:
                    refl_obj = json.loads(reflection or "{}")
                except Exception:
                    refl_obj = {}
            except Exception:
                rs = {}
                for i, t in enumerate(outputs):
                    n = names[i] if i < len(names) else f"agent-{i}"
                    rs[n] = min(1.0, max(0.0, len(t) / 1000.0))
                refl_obj = {"mode": mode, "reflection_scores": rs, "notes": []}
        else:
            refl_obj = {"mode": mode, "reflection_scores": {}, "notes": []}
        scores = scores
        fused = None
        weights = {}
        if options.get("fusion", True):
            fusion_card = get_agent_card("fusion")
            fus_client = factory.create(fusion_card)
            fus_payload = json.dumps({
                "names": names,
                "outputs": outputs,
                "base_weights": {n: SCORING_WEIGHTS.get(n, 0.0) for n in names},
                "reflection_scores": refl_obj.get("reflection_scores", {}),
                "auto_scores": scores,
            }, ensure_ascii=False)
            try:
                async for event in fus_client.send_message(Message(role=Role.user, parts=[Part(root=TextPart(text=fus_payload))])):
                    if hasattr(event, "parts"):
                        from a2a.utils import get_message_text
                        res = get_message_text(event)
                        try:
                            obj = json.loads(res)
                        except Exception:
                            obj = {}
                        fused = obj.get("fused")
                        weights = obj.get("weights") or {}
                        break
                    break
            except Exception:
                fused = None
            if fused is None:
                norm = sum(SCORING_WEIGHTS.get(n, 0.0) for n in names) or 1.0
                weights = {n: (SCORING_WEIGHTS.get(n, 0.0) / norm) for n in names}
                parts = []
                for i, t in enumerate(outputs):
                    n = names[i] if i < len(names) else f"agent-{i}"
                    parts.append(f"[{n}:{weights.get(n, 0.0):.2f}] {t}")
                fused = "\n".join(parts)
        else:
            fused = "\n".join(outputs)
            weights = {}
        return {"names": names, "outputs": outputs, "scores": scores, "reflection": refl_obj, "fusion": fused, "weights": weights}