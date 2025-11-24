import operator
import re
from typing import Any, Dict

import yaml


OP_MAP = {
    "<=": operator.le,
    ">=": operator.ge,
    "<": operator.lt,
    ">": operator.gt,
    "==": operator.eq,
}


def load_rules(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_condition(value: str):
    m = re.match(r"(<=|>=|<|>|==)\s*(.+)", str(value).strip())
    if not m:
        return None
    op, rhs = m.group(1), m.group(2)
    try:
        rhs_val = float(rhs)
    except Exception:
        rhs_val = rhs
    return OP_MAP[op], rhs_val


def match_payload_condition(payload: Dict[str, Any], rule_payload: Dict[str, Any]) -> bool:
    for k, cond in (rule_payload or {}).items():
        val = payload.get(k)
        if isinstance(cond, str):
            parsed = parse_condition(cond)
            if parsed:
                op, rhs = parsed
                try:
                    if val is None:
                        return False
                    if not op(float(val), float(rhs)):
                        return False
                except Exception:
                    return False
            else:
                if str(val) != str(cond):
                    return False
        else:
            if val != cond:
                return False
    return True


def match_instant_rule(event: Dict, rule: Dict) -> bool:
    m = rule.get("match", {})
    if "type" in m and event.get("type") != m["type"]:
        return False
    return match_payload_condition(event.get("payload", {}), m.get("payload", {}))