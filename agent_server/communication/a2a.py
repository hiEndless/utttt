from typing import List, Dict, Any
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

    async def reflect(self, texts: List[str]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for t in texts:
            score = min(1.0, max(0.0, len(t) / 1000.0))
            results.append({"text": t, "score": score})
        return results