def build_indicator_view(all_indicators: dict, plugin) -> dict:
    """
    依据插件声明的 tf_scope / indicators 构造裁剪视图。
    约定：
    - ema: 使用 ema12 作为 value，prev 使用 prev.ema12
    - macd: 提供 dif/dea/macd 以及 hist(=macd/2)，prev_hist(=prev.macd/2)
    - 其他指标直接透传value与prev（若存在）
    """
    view = {}
    for tf in getattr(plugin, "tf_scope", []) or []:
        if tf not in all_indicators:
            continue
        view[tf] = {}
        for ind in getattr(plugin, "indicators", []) or []:
            data = (all_indicators.get(tf, {}) or {}).get(ind, {}) or {}
            prev = data.get("prev") or {}
            if ind == "ema":
                view[tf][ind] = {
                    "value": data.get("ema12"),
                    "prev": (prev or {}).get("ema12"),
                }
            elif ind == "macd":
                macd_val = data.get("macd")
                prev_macd = (prev or {}).get("macd")
                view[tf][ind] = {
                    "dif": data.get("dif"),
                    "dea": data.get("dea"),
                    "macd": macd_val,
                    "hist": (macd_val / 2.0) if isinstance(macd_val, (int, float)) else None,
                    "prev_dif": (prev or {}).get("dif"),
                    "prev_dea": (prev or {}).get("dea"),
                    "prev_macd": prev_macd,
                    "prev_hist": (prev_macd / 2.0) if isinstance(prev_macd, (int, float)) else None,
                }
            else:
                # 直接透传常见字段
                v = {}
                for k, val in (data or {}).items():
                    if k == "prev":
                        continue
                    v[k] = val
                if prev:
                    v["prev"] = prev
                view[tf][ind] = v
    return view


if __name__ == "__main__":
    import json
    from event_center.indicators_event.engine.indicator_loader import load_all_indicators
    from event_center.indicators_event.plugins.ema_macd_combo import EMAMACDCombo

    indicators = load_all_indicators("BTCUSDT")
    plugin = EMAMACDCombo()
    view = build_indicator_view(indicators, plugin)
    print(json.dumps(view, ensure_ascii=False, indent=2))
