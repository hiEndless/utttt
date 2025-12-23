import json
import re


def _extract_json_from_text(text: str):
    if not isinstance(text, str):
        return None
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if m:
        candidate = m.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
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