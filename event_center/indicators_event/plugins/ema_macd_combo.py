from event_center.indicators_event.plugins.base import Plugin
import time


class EMAMACDCombo(Plugin):
    name = "ema_macd_combo"

    tf_scope = ["1m", "5m"]
    indicators = ["ema", "macd", "williams_r", "mfi"]
    requires_prev = True

    def generate(self, symbol: str, indicator_view: dict):
        res = []

        for tf in self.tf_scope:
            ema = (indicator_view.get(tf, {}) or {}).get("ema", {}) or {}
            macd = (indicator_view.get(tf, {}) or {}).get("macd", {}) or {}

            if ema.get("value") is not None and ema.get("prev") is not None \
               and macd.get("hist") is not None and macd.get("prev_hist") is not None \
               and ema["value"] > ema["prev"] and macd["hist"] > macd["prev_hist"]:
                res.append({
                    "plugin": self.name,
                    "symbol": symbol,
                    "tf": tf,
                    "direction": "bullish",
                    "strength": 1,
                    "src": "ema_macd",
                    "ts": int(time.time()),
                })

        return res


if __name__ == "__main__":
    indicator_view = {
        "1m": {
            "ema": {
                "value": 87226.64791531,
                "prev": 87231.36571809361
            },
            "macd": {
                "dif": -13.854437824324123,
                "dea": -12.182101316820203,
                "macd": -3.3446730150078388,
                "hist": -1.6723365075039194,
                "prev_dif": -12.320823291447596,
                "prev_dea": -11.764017189944223,
                "prev_macd": -1.1136122030067455,
                "prev_hist": -0.5568061015033727
            }
        },
        "5m": {
            "ema": {
                "value": 87236.8888723178,
                "prev": 87244.86866728467
            },
            "macd": {
                "dif": -12.403145720891189,
                "dea": -22.123527140067466,
                "macd": 19.440762838352555,
                "hist": 9.720381419176277,
                "prev_dif": -8.926712197106099,
                "prev_dea": -24.553622494861532,
                "prev_macd": 31.253820595510867,
                "prev_hist": 15.626910297755433
            }
        }
    }
    res = EMAMACDCombo().generate("BTCUSDT", indicator_view)
    print(res)
