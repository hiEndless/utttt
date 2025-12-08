from agno.tools import tool


@tool
def web_json(url: str) -> dict:
    return {"ok": True, "source": "mock", "url": url, "data": {"value": 123}}


@tool
def calc_rsi(prices: list, period: int = 14) -> float:
    return 50.0


@tool
def get_force_stats(symbol: str) -> dict:
    return {"symbol": symbol, "ts": 1765097881177, "sell": 12, "buy": 0, "buy_qty": 0, "sell_qty": 10}
