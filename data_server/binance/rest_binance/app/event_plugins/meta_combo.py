import os


def _try_load_yaml(path):
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def load_weights(base_dir):
    path = os.path.join(base_dir, "config", "meta_weights.yml")
    data = _try_load_yaml(path)
    if data:
        return data
    return {
        "global": {
            "trigger_weight": 1,
            "pattern_weight": 2,
            "min_strength": 2,
        },
        "plugins": {
            "rsi_kdj_combo": {
                "triggers": {
                    "rsi_rebound": 2,
                    "kdj_cross": 2,
                    "kdj_extreme": 1,
                    "rsi_break_50": 1,
                    "vol_confirm": 1,
                },
                "patterns": {
                    "rsi_bull_div": 3,
                    "second_bottom": 2,
                    "rsi_stack": 2,
                    "wave_sync": 2,
                    "top_div_kdj": 3,
                },
            },
            "kdj_boll_combo": {
                "triggers": {
                    "bull_cross_mid": 2,
                    "low_reversal_mid_break": 2,
                    "near_lower_touch": 1,
                    "double_bottom_candidate": 2,
                    "band_narrow": 1,
                    "trend_confirm_up": 2,
                },
                "patterns": {
                    "near_lower": 2,
                    "band_narrow_pattern": 2,
                    "mid_retest": 2,
                    "double_bottom_confirm": 3,
                },
            },
            "boll_vol_combo": {
                "triggers": {
                    "upper_breakout_vol": 3,
                    "lower_breakout_vol": 3,
                    "mid_retest_low_vol": 2,
                    "band_squeeze_atr_up": 2,
                    "band_squeeze_atr_down": 2,
                    "vol_spike": 1,
                    "vol_collapse": 1,
                    "band_squeeze": 1,
                },
                "patterns": {},
            },
            "ema_macd_extended_combo": {
                "triggers": {
                    "ema_golden_cross": 3,
                    "ema_dead_cross": 3,
                    "macd_hist_turn_positive": 2,
                    "macd_hist_turn_negative": 2,
                    "macd_signal_cross_up": 2,
                    "macd_signal_cross_down": 2,
                    "dif_cross_zero_up": 2,
                    "dif_cross_zero_down": 2,
                    "ema_triple_golden": 3,
                    "ema_triple_dead": 3,
                    "macd_bull_momentum": 2,
                    "macd_bear_momentum": 2,
                    "bullish_divergence": 3,
                    "bearish_divergence": 3,
                },
                "patterns": {},
            },
            "triple_rsi_ema_macd": {
                "triggers": {
                    "rsi_rebound": 2,
                    "rsi_fall": 2,
                    "ema_golden_cross": 3,
                    "ema_death_cross": 3,
                    "macd_golden_cross": 2,
                    "macd_death_cross": 2,
                },
                "patterns": {
                    "rsi_bull_div": 3,
                    "macd_bull_div": 3,
                    "rsi_bear_div": 3,
                    "macd_bear_div": 3,
                },
            },
            "rsi_macd_combo": {
                "triggers": {
                    "rsi_macd_reversal": 3,
                    "rsi_oversold_macd_zero": 2,
                    "rsi50_macd_zero_break": 2,
                    "rsi_pullback_bull": 1,
                    "rsi_oversold_hist_decay": 1,
                    "rsi_strong_bull": 2,
                    "rsi_macd_reversal_bear": 3,
                    "rsi_overbought_macd_zero": 2,
                    "rsi50_macd_zero_break_bear": 2,
                    "rsi_pullback_bear": 1,
                    "rsi_overbought_hist_decay": 1,
                    "rsi_strong_bear": 2,
                },
                "patterns": {
                    "rsi_bull_divergence": 3,
                    "macd_bull_divergence": 3,
                    "rsi_bear_divergence": 3,
                    "macd_bear_divergence": 3,
                },
            },
        },
    }


def score_events(events, weights):
    g = weights.get("global", {})
    tw = g.get("trigger_weight", 1)
    pw = g.get("pattern_weight", 2)
    min_strength = g.get("min_strength", 2)

    # 新增：方向一致性相关参数
    dir_bonus = g.get("direction_bonus", 1.2)
    dir_penalty = g.get("direction_penalty", 0.7)
    conflict_threshold = g.get("conflict_threshold", 0.4)

    per_plugin = {}
    total = 0
    top = []

    # 新增：方向统计
    bull_count = 0
    bear_count = 0

    # ---------------------------
    # 第一次遍历：统计方向数量
    # ---------------------------
    for ev in events:
        side = ev.get("payload", {}).get("side")
        if side == "bullish":
            bull_count += 1
        elif side == "bearish":
            bear_count += 1

    total_count = max(bull_count + bear_count, 1)
    bull_ratio = bull_count / total_count
    bear_ratio = bear_count / total_count

    # ---------------------------
    # 第二次遍历：按方向一致性调整评分
    # ---------------------------
    for ev in events:
        payload = ev.get("payload", {})
        plugin = payload.get("plugin") or ev.get("payload", {}).get("signal", "unknown")
        side = payload.get("side")
        triggers = payload.get("triggers", {})
        patterns = payload.get("patterns", {})

        base = weights.get("plugins", {}).get(plugin, {})
        tmap = base.get("triggers", {})
        pmap = base.get("patterns", {})

        # ---------------------------
        # 计算基础分
        # ---------------------------
        score = 0
        for k in triggers.keys():
            score += tw * (tmap.get(k, 1))
        for k in patterns.keys():
            score += pw * (pmap.get(k, 2))

        # 不达基础强度的话直接跳过
        strength = payload.get("strength") or (len(triggers) * tw + len(patterns) * pw)
        if strength < min_strength:
            continue

        # ---------------------------
        # 方向一致性规则
        # ---------------------------
        if side == "bullish":
            # bullish 插件占比高 → 加分
            score *= dir_bonus ** bull_ratio

            # bearish 过多 → 扣分
            if bear_ratio > conflict_threshold:
                score *= dir_penalty

        elif side == "bearish":
            score *= dir_bonus ** bear_ratio
            if bull_ratio > conflict_threshold:
                score *= dir_penalty

        # ---------------------------
        # 汇总
        # ---------------------------
        per_plugin.setdefault(plugin, 0)
        per_plugin[plugin] += score
        total += score

        top.append({
            "plugin": plugin,
            "side": side,
            "score": score,
            "signal": payload.get("signal")
        })

    # 返回 top10
    top = sorted(top, key=lambda x: x["score"], reverse=True)[:10]

    return {
        "total": total,
        "per_plugin": per_plugin,
        "top": top,
        "count": len(events),
        "bull_ratio": bull_ratio,
        "bear_ratio": bear_ratio,
    }


def build_dashboard(scores):
    return {"total": scores["total"], "per_plugin": scores["per_plugin"], "top": scores["top"], "events_count": scores["count"]}