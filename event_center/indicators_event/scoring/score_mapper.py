def factor_to_score(factor, tf_weights, strength_weights):
    base = 1.0 if factor["direction"] != "neutral" else 0.0

    tf_w = tf_weights.get(factor["tf"], 1.0)
    st_w = strength_weights.get(factor["strength"], 1.0)

    signed = base * tf_w * st_w
    if factor["direction"] == "bearish":
        signed = -signed

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
    }
