from typing import List, Dict

from agent_server.communication import A2ACommunicator
from agent_server.config import SCORING_WEIGHTS
from agent_server.teams.fusion import weighted_fusion
from agent_server.teams.scoring import auto_score


class TeamOrchestrator:
    def __init__(self):
        self.a2a = A2ACommunicator()

    async def run(self, mode: str, agents: List, query: str) -> Dict:
        # agents can be either list of agent instances, or dicts with agent+card
        cards = []
        if agents and isinstance(agents[0], dict):
            names = [a.get("name") or getattr(a["agent"], "name", "agent") for a in agents]
            cards = [a.get("card") for a in agents]
            prompts = []
            import uuid
            from a2a.client import ClientFactory, ClientConfig
            from a2a.types import Message, Part, TextPart, Role, TransportProtocol
            from a2a.utils import get_message_text
            config = ClientConfig(
                streaming=False,
                supported_transports=[TransportProtocol.jsonrpc],
                use_client_preference=False,
            )
            factory = ClientFactory(config)
            for i, a in enumerate(agents):
                card = cards[i]
                client = factory.create(card)
                msg = Message(role=Role.user, parts=[Part(root=TextPart(text=query))], message_id=str(uuid.uuid4()))
                async for event in client.send_message(msg):
                    if hasattr(event, "parts"):
                        prompts.append(get_message_text(event))
                        break
                    break
        else:
            raise RuntimeError("Agents must be provided with cards for A2A communication")
        if mode == "debate":
            outputs = await self.a2a.debate(prompts)
        elif mode == "delphi":
            outputs = await self.a2a.delphi(prompts)
        elif mode == "n_variant":
            outputs = await self.a2a.n_variant(prompts)
        else:
            outputs = prompts
        scores = auto_score(outputs)
        fused, weights = weighted_fusion(outputs, SCORING_WEIGHTS, names)
        return {"names": names, "outputs": outputs, "scores": scores, "fusion": fused, "weights": weights}