import json


class MemoryExpert:
    name = "memory"

    async def run(self, query: str) -> str:
        try:
            obj = json.loads(query or "{}")
        except Exception:
            obj = {}
        trade_id = str(obj.get("trade_id") or obj.get("id") or obj.get("symbol") or "")
        fused = obj.get("fused")
        outputs = obj.get("outputs") or []
        reflection = obj.get("reflection") or {}
        weights = obj.get("weights") or {}
        event_payload = obj.get("event") or obj.get("payload") or {}
        from agent_server.memory.store import MemoryCoordinator, MemoryStore
        mc = MemoryCoordinator()
        if not trade_id:
            # allow memory agent to be called for preview only
            return json.dumps({"ok": False, "error": "missing trade_id"}, ensure_ascii=False)
        await mc.update(trade_id, fused, outputs, reflection, weights, event_payload)
        store = MemoryStore()
        ctx = await store.get_model_context(trade_id)
        return json.dumps({"ok": True, "trade_id": trade_id, "context": ctx}, ensure_ascii=False)