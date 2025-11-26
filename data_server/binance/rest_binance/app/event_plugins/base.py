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