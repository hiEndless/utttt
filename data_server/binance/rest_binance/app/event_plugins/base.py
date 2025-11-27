import uuid
import time


def last_close(kline):
    try:
        return float(kline[-1][4])
    except Exception:
        return None


def last_ts(kline):
    try:
        return int(kline[-1][6])
    except Exception:
        try:
            return int(kline[-1][0])
        except Exception:
            return int(time.time())
    

def build_event(symbol, kline, signal, payload, interval):
    return {
        "event_id": uuid.uuid4().hex,
        "timestamp": last_ts(kline),
        "symbol": symbol,
        "interval": interval,
        "type": "indicator_signal",
        "payload": {"signal": signal, **payload},
    }


def prev_close(kline):
    try:
        return float(kline[-2][4]) if len(kline) >= 2 else None
    except Exception:
        return None


class EventPlugin:
    def generate(self, symbol, kline, ind, prev_ind, interval):
        return []

    def supports(self, symbol, interval, kline, ind):
        try:
            # interval filter
            if hasattr(self, "supported_intervals"):
                si = getattr(self, "supported_intervals") or []
                if si and interval not in si:
                    return False

            # required indicators presence
            req = getattr(self, "required_indicators", None)
            if isinstance(req, (list, tuple)):
                for key in req:
                    if key not in ind:
                        return False

            # generic volatility gating
            vol = ind.get("vol", {})
            adx = vol.get("adx")
            atr = vol.get("atr")
            close = last_close(kline)

            min_adx = getattr(self, "min_adx", None)
            if min_adx is not None:
                if adx is None or adx < min_adx:
                    return False

            min_atr_ratio = getattr(self, "min_atr_ratio", None)
            if min_atr_ratio is not None:
                if close is None or atr is None:
                    return False
                if close == 0:
                    return False
                if (atr / close) < min_atr_ratio:
                    return False

            return True
        except Exception:
            return True