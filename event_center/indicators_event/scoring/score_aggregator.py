import os, yaml


def _load_yaml(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return {}


def _get_config_dir():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(base_dir, "config")


def _discount(scores_by_cls):
    cfg = _load_yaml(os.path.join(_get_config_dir(), "combo_discount.yaml")) or {}
    mode = (cfg.get("mode") or "fixed").lower()
    if mode == "log":
        import math
        k = float(cfg.get("k", 1.0))
        # scores_by_cls: list of numeric scores
        total = 0.0
        for i, s in enumerate(sorted(scores_by_cls, key=lambda x: abs(x), reverse=True), start=1):
            total += s * (1.0 + math.log(max(1, i)) * k) / (1.0 + math.log(max(1, len(scores_by_cls))) * k)
        return total
    else:
        weights = cfg.get("fixed_weights") or [1.0, 0.7, 0.4, 0.2]
        total = 0.0
        for i, s in enumerate(sorted(scores_by_cls, key=lambda x: abs(x), reverse=True)):
            w = weights[i] if i < len(weights) else weights[-1] * 0.5
            total += s * w
        return total


def aggregate_scores(scores):
    cfg_dir = _get_config_dir()
    buckets_cfg = _load_yaml(os.path.join(cfg_dir, "tf_buckets.yaml")) or {
        "short": ["1m", "5m"],
        "mid": ["15m", "30m", "1h"],
        "long": ["2h", "4h", "1d"],
    }
    policy = _load_yaml(os.path.join(cfg_dir, "combo_discount.yaml")) or {}
    div_degrade = float(policy.get("divergence_degrade", 0.8))
    strong_thr = float(policy.get("strong_opposite_threshold", 3.0))

    tf_groups = {}
    for s in scores:
        tf_groups.setdefault(s["tf"], []).append(s)

    tf_sums = {}
    tf_dirs = {}
    for tf, items in tf_groups.items():
        # per tf: reduce by class — keep max abs score per class
        cls_best = {}
        for it in items:
            cls = it.get("cls") or "unknown"
            sc = float(it["score"])
            prev = cls_best.get(cls)
            if prev is None or abs(sc) > abs(prev):
                cls_best[cls] = sc
        # discount across classes
        tf_sum = _discount(list(cls_best.values()))
        tf_sums[tf] = tf_sum
        tf_dirs[tf] = "bullish" if tf_sum > 0 else ("bearish" if tf_sum < 0 else "neutral")

    # bucket aggregation
    bucket_scores = {}
    bucket_dirs = {}
    for bname, tfs in buckets_cfg.items():
        val = sum(tf_sums.get(tf, 0.0) for tf in tfs)
        bucket_scores[bname] = val
        bucket_dirs[bname] = "bullish" if val > 0 else ("bearish" if val < 0 else "neutral")

    # structural judgement
    dirs = [bucket_dirs.get("short"), bucket_dirs.get("mid"), bucket_dirs.get("long")]
    # determine divergence
    non_neutral = [d for d in dirs if d != "neutral"]
    divergence = len(set(non_neutral)) > 1
    raw_total = sum(bucket_scores.values())
    direction = "bullish" if raw_total > 0 else ("bearish" if raw_total < 0 else "neutral")

    final_forbidden = False
    # optional cls cross-tf decay
    enable_decay = bool(policy.get("enable_cls_decay", True))
    decay_base = float(policy.get("cls_decay_base", 0.6))
    decayed_total = raw_total
    if enable_decay:
        # group by cls over original scores
        cls_groups = {}
        for s in scores:
            cls = s.get("cls") or "unknown"
            cls_groups.setdefault(cls, []).append(s)
        decayed_total = 0.0
        for cls, items in cls_groups.items():
            items = sorted(items, key=lambda x: abs(float(x["score"])), reverse=True)
            cls_score = 0.0
            for i, s in enumerate(items):
                decay = 1.0 if i == 0 else (decay_base ** i)
                cls_score += float(s["score"]) * decay
            decayed_total += cls_score

    total = decayed_total
    if divergence:
        # Apply degradation primarily to conflicting buckets
        total = 0.0
        for bname, val in bucket_scores.items():
            dir_b = bucket_dirs.get(bname)
            if dir_b != "neutral" and dir_b != direction:
                total += val * div_degrade
            else:
                total += val
    # strong opposite: long opposes combined short+mid strongly
    long_val = bucket_scores.get("long", 0.0)
    short_mid = bucket_scores.get("short", 0.0) + bucket_scores.get("mid", 0.0)
    if long_val != 0.0 and short_mid != 0.0 and (long_val * short_mid) < 0 and abs(long_val) >= strong_thr:
        final_forbidden = True

    # final direction should reflect final total
    direction = "bullish" if total > 0 else ("bearish" if total < 0 else "neutral")
    return {
        "total": total,
        "direction": direction,
        "raw_total": raw_total,
        "tf_sums": tf_sums,
        "tf_dirs": tf_dirs,
        "bucket_scores": bucket_scores,
        "bucket_dirs": bucket_dirs,
        "divergence": divergence,
        "final_forbidden": final_forbidden,
        "timeframe_alignment": {
            "bullish": [tf for tf, d in tf_dirs.items() if d == "bullish"],
            "bearish": [tf for tf, d in tf_dirs.items() if d == "bearish"],
        },
    }
