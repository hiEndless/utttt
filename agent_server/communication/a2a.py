from typing import List
from a2a.utils import new_agent_text_message, get_message_text


class A2ACommunicator:
    def _wrap(self, sender: str, content: str):
        return new_agent_text_message(text=content)

    async def debate(self, prompts: List[str]) -> List[str]:
        transcript = []
        for i, p in enumerate(prompts):
            msg = self._wrap(sender=f"agent-{i}", content=p)
            transcript.append(msg)
        return [get_message_text(m) for m in transcript]

    async def delphi(self, prompts: List[str]) -> List[str]:
        merged = "\n".join(prompts)
        msg = self._wrap(sender="consensus", content=merged)
        return [get_message_text(msg)]

    async def n_variant(self, prompts: List[str]) -> List[str]:
        variants = []
        for i, p in enumerate(prompts):
            variants.append(self._wrap(sender=f"variant-{i}", content=p))
        return [get_message_text(m) for m in variants]


class A2ASession:
    async def broadcast(self, agents: List, query: str) -> List[str]:
        import uuid
        from a2a.client import ClientFactory, ClientConfig
        from a2a.types import Message, Part, TextPart, Role, TransportProtocol
        from a2a.utils import get_message_text
        config = ClientConfig(streaming=False, supported_transports=[TransportProtocol.jsonrpc], use_client_preference=False)
        factory = ClientFactory(config)
        outputs: List[str] = []
        for i, a in enumerate(agents):
            card = a.get("card")
            got = None
            if card is not None:
                try:
                    client = factory.create(card)
                    msg = Message(role=Role.user, parts=[Part(root=TextPart(text=query))], message_id=str(uuid.uuid4()))
                    async for event in client.send_message(msg):
                        if hasattr(event, "parts"):
                            got = get_message_text(event)
                            break
                        break
                except Exception:
                    got = None
            if got is None:
                try:
                    res = a["agent"].run(query)
                    if hasattr(res, "__await__"):
                        res = await res
                    outputs.append(str(res))
                    continue
                except Exception:
                    outputs.append("")
                    continue
            outputs.append(str(got))
        return outputs
