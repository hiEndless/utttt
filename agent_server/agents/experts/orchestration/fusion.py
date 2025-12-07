import json
from typing import Dict, List


class FusionExpert:
    name = "fusion"

    async def run(self, query: str) -> str:
        try:
            payload = json.loads(query)
        except Exception:
            payload = {}
        names: List[str] = payload.get("names") or []
        outputs: List[str] = payload.get("outputs") or []
        base_weights: Dict[str, float] = payload.get("base_weights") or {}
        reflection_scores: Dict[str, float] = payload.get("reflection_scores") or {}
        auto_scores: Dict[int, float] = payload.get("auto_scores") or {}
        combined: Dict[str, float] = {}
        for i, n in enumerate(names):
            bw = base_weights.get(n, 0.0)
            rs = reflection_scores.get(n, 0.0)
            ascore = auto_scores.get(i, 0.0)
            combined[n] = bw * (0.5 * rs + 0.5 * ascore)
        norm = sum(combined.get(n, 0.0) for n in names) or 1.0
        weights = {n: (combined.get(n, 0.0) / norm) for n in names}
        parts: List[str] = []
        for i, t in enumerate(outputs):
            n = names[i] if i < len(names) else f"agent-{i}"
            parts.append(f"[{n}:{weights.get(n, 0.0):.2f}] {t}")
        fused = "\n".join(parts)
        return json.dumps({"fused": fused, "weights": weights}, ensure_ascii=False)