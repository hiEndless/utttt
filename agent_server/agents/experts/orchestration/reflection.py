import json


class ReflectionExpert:
    name = "reflection"

    async def run(self, query: str) -> str:
        try:
            payload = json.loads(query)
        except Exception:
            payload = {}
        names = payload.get("names") or []
        outputs = payload.get("outputs") or []
        mode = payload.get("mode") or "default"
        scores = {}
        notes = []
        for i, t in enumerate(outputs):
            n = names[i] if i < len(names) else f"agent-{i}"
            s = min(1.0, max(0.0, len(t) / 1000.0))
            scores[n] = s
            notes.append({"name": n, "insight": t[:160]})
        result = {"mode": mode, "reflection_scores": scores, "notes": notes}
        return json.dumps(result, ensure_ascii=False)