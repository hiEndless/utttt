import os, yaml

_CLASS_CACHE = None

def _load_class_map():
    global _CLASS_CACHE
    if _CLASS_CACHE is not None:
        return _CLASS_CACHE
    try:
        base_dir = os.path.dirname(os.path.dirname(__file__))
        cfg_dir = os.path.join(base_dir, "config")
        path = os.path.join(cfg_dir, "indicator_class_map.yaml")
        with open(path, "r", encoding="utf-8") as f:
            _CLASS_CACHE = yaml.safe_load(f) or {}
    except Exception:
        _CLASS_CACHE = {}
    return _CLASS_CACHE

def _infer_cls(factor):
    m = _load_class_map() or {}
    src = (factor.get("src") or "").lower()
    plug = (factor.get("plugin") or "").lower()
    by_ind = (m.get("by_indicator") or {})
    by_plug = (m.get("by_plugin") or {})
    # try src first
    for cls, names in by_ind.items():
        if isinstance(names, list) and src in [n.lower() for n in names]:
            return cls
    # fallback plugin mapping
    for cls, names in by_plug.items():
        if isinstance(names, list) and plug in [n.lower() for n in names]:
            return cls
    return None

def factor_to_score(factor, tf_weights, strength_weights):
    base = 1.0 if factor["direction"] != "neutral" else 0.0

    tf_w = tf_weights.get(factor["tf"], 1.0)
    st_w = strength_weights.get(factor["strength"], 1.0)

    signed = base * tf_w * st_w
    if factor["direction"] == "bearish":
        signed = -signed
    cls = factor.get("cls") or _infer_cls(factor) or "unknown"

    return {
        "symbol": factor["symbol"],
        "plugin": factor["plugin"],
        "tf": factor["tf"],
        "direction": factor["direction"],
        "score": signed,
        "base": base,
        "tf_weight": tf_w,
        "strength_weight": st_w,
        "ts": factor["ts"],
        "cls": cls,
    }
