import json
import re
from json_repair import repair_json


def _extract_json_from_text(text: str):
    if not isinstance(text, str):
        return None
    
    # 1. Try standard regex extraction first (fastest)
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if m:
        candidate = m.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            # Fallback to repair_json
            try:
                return repair_json(candidate, return_objects=True)
            except Exception:
                pass

    # 2. Try finding brackets
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            try:
                return repair_json(candidate, return_objects=True)
            except Exception:
                pass
    
    # 3. Last resort: try repairing the whole text (if it's a messy JSON without clear boundaries)
    try:
        # skip_json_loads=True because we likely already failed or text is messy
        return repair_json(text, return_objects=True, skip_json_loads=True)
    except Exception:
        return None


def _ensure_json_serializable(obj):
    try:
        json.dumps(obj, ensure_ascii=False)
        return obj
    except TypeError:
        return {"raw": str(obj)}


def _json_dumps_safe(obj):
    try:
        return json.dumps(obj, ensure_ascii=False)
    except TypeError:
        return json.dumps({"raw": str(obj)}, ensure_ascii=False)