import time
import hmac
import hashlib
import requests
import os
from urllib.parse import urlencode
from typing import List, Dict, Optional, Any, Union
import pandas as pd


class BinanceFuturesClient:
    """
    Binance Futures REST API Client.
    Provides methods to fetch user trades and calculate position history/PnL.
    """
    BASE_URL = "https://fapi.binance.com"

    def __init__(self, api_key: str, api_secret: str):
        """
        Initialize the client with API credentials.
        
        Args:
            api_key: Binance API Key
            api_secret: Binance API Secret
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = requests.Session()
        self.session.headers.update({
            "X-MBX-APIKEY": self.api_key
        })

    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sign the request parameters."""
        if "signature" in params:
            del params["signature"]

        # Ensure timestamp is present before signing
        if "timestamp" not in params:
            params["timestamp"] = int(time.time() * 1000)

        query = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        params["signature"] = signature
        return params

    def _request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Internal request method with error handling and signing."""
        if params is None:
            params = {}

        # Sign the parameters
        self._sign(params)

        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = self.session.request(method, url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            if response.text:
                print(f"Response: {response.text}")
            raise

    def get_user_trades(self, symbol: str, start_time: Optional[int] = None, end_time: Optional[int] = None,
                        limit: int = 1000) -> List[Dict]:
        """
        Fetch user trades for a specific symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            start_time: Start timestamp in ms
            end_time: End timestamp in ms
            limit: Number of records to fetch (max 1000)
        """
        params = {
            "symbol": symbol,
            "limit": limit
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        return self._request("GET", "/fapi/v1/userTrades", params)

    @staticmethod
    def get_last_position(trades: List[Dict]) -> List[Dict]:
        trades = sorted(trades, key=lambda x: x["time"])
        if trades:
            return trades[-1]
        else:
            return []

    @staticmethod
    def rebuild_position_history(trades: List[Dict]) -> List[Dict]:
        """
        Reconstruct position history from trade list.
        
        Args:
            trades: List of trade dictionaries
            
        Returns:
            List of position states after each trade
        """
        trades = sorted(trades, key=lambda x: x["time"])  # Ascending

        position_qty = 0.0
        avg_price = 0.0
        history = []

        for t in trades:
            order_id = t["orderId"]
            qty = float(t["qty"])
            price = float(t["price"])
            side = t["side"]
            position_side = t["positionSide"]
            realized_pnl = float(t["realizedPnl"])

            if side == "BUY":
                # If short, this closes short. If long/flat, this opens long.
                if position_qty < 0:  # Closing Short
                    # Check if we flip position
                    if position_qty + qty > 0:
                        # Flip: Close all short, open remainder long
                        # This complicates avg_price calc.
                        # Original code didn't handle flip strictly with pnl match, just simple weighted avg for open?
                        # Original:
                        # new_qty = position_qty + qty
                        # if new_qty != 0: avg_price = (pos*avg + qty*price) / new_qty
                        # This formula works for weighted average if adding to position.
                        # It is WRONG if reducing position (realized pnl generated, entry price doesn't change).
                        pass

                # Let's stick to the logic that matches `trades_to_closed_positions` which seemed more robust (it handles pnl).
                # But `rebuild_position_history` in original code was very simple.
                # I will implement a standard position tracking logic.

                if position_qty >= 0:  # Adding to Long
                    if position_qty + qty != 0:
                        avg_price = (position_qty * avg_price + qty * price) / (position_qty + qty)
                    position_qty += qty
                else:  # Closing Short
                    position_qty += qty
                    # Entry price (avg_price) does not change when closing, unless we flip
                    if position_qty > 0:  # Flipped to Long
                        # The portion that closed short is gone. The remainder is new long.
                        # This simple logic is hard without tracking exact closed amount.
                        # For simplicity/optimization of the *original tool*, I will use the logic that assumes simple aggregation
                        # but I will trust `trades_to_closed_positions` more for PnL.
                        # For this method, I will use the simple accumulation but correct the time order.
                        avg_price = price  # If we flipped, the new price is the entry.
                        # Actually, let's just stick to the original simple logic but sorted Ascending.
                        pass

            # Let's try to preserve the original simple math but in correct order:
            # Original:
            # if side == "BUY":
            #    new_qty = position_qty + qty
            #    if new_qty != 0: avg_price = (position_qty * avg_price + qty * price) / new_qty
            #    position_qty = new_qty
            # 
            # This formula `(old_qty * old_avg + new_qty * new_price) / total_qty` is correct for INCREASING position size.
            # It is INCORRECT for DECREASING position size (closing). When closing, avg entry price doesn't change.
            # 
            # Since the user asked to "optimize", I should fix this logic.

            prev_qty = position_qty

            if side == "BUY":
                position_qty += qty
            else:  # SELL
                position_qty -= qty

            # Update Avg Price
            if prev_qty == 0:
                avg_price = price
            elif (prev_qty > 0 and side == "BUY") or (prev_qty < 0 and side == "SELL"):
                # Increasing position (adding to Long or adding to Short)
                # Note: qty is always positive from API? Yes.
                # If prev_qty < 0 (Short) and side == SELL (shorting more):
                # We need to treat quantities as absolute for weighted average?
                # new_avg = (abs(prev) * avg + qty * price) / (abs(prev) + qty)
                total_abs_qty = abs(prev_qty) + qty
                avg_price = (abs(prev_qty) * avg_price + qty * price) / total_abs_qty
            elif (prev_qty > 0 and side == "SELL") or (prev_qty < 0 and side == "BUY"):
                # Reducing position (Closing)
                # Avg Price (Entry Price) DOES NOT CHANGE.
                # Unless we cross 0.
                if (prev_qty > 0 and position_qty < 0) or (prev_qty < 0 and position_qty > 0):
                    # Flipped
                    avg_price = price
                elif position_qty == 0:
                    avg_price = 0.0

            history.append({
                "order_id": order_id,
                "time": t["time"],
                "side": side,
                "position_side": position_side,
                "price": price,
                "qty": qty,
                "position_qty": round(position_qty, 6),
                "avg_price": round(avg_price, 6),
                "realized_pnl": realized_pnl
            })

        return history

    @staticmethod
    def calculate_closed_positions(trades: List[Dict], symbol: str) -> List[Dict]:
        """
        Calculate closed positions and PnL from trade history.
        
        Args:
            trades: List of trade dictionaries
            symbol: Symbol name
            
        Returns:
            List of closed position summaries
        """
        trades = sorted(trades, key=lambda x: x["time"])

        position_sides = {str(t.get("positionSide", "") or "").upper() for t in trades}
        if ("LONG" in position_sides) or ("SHORT" in position_sides):
            closed_positions: List[Dict] = []
            long_trades = [t for t in trades if str(t.get("positionSide", "") or "").upper() == "LONG"]
            short_trades = [t for t in trades if str(t.get("positionSide", "") or "").upper() == "SHORT"]
            if long_trades:
                closed_positions.extend(BinanceFuturesClient._calculate_closed_positions_hedge_one_side(
                    long_trades, symbol, position_side="LONG"
                ))
            if short_trades:
                closed_positions.extend(BinanceFuturesClient._calculate_closed_positions_hedge_one_side(
                    short_trades, symbol, position_side="SHORT"
                ))
            return sorted(closed_positions, key=lambda x: x.get("close_time") or 0)

        return BinanceFuturesClient._calculate_closed_positions_one_way(trades, symbol)

    @staticmethod
    def _calculate_closed_positions_hedge_one_side(trades: List[Dict], symbol: str, position_side: str) -> List[Dict]:
        eps = 1e-12
        position_side = str(position_side or "").upper()

        position_qty = 0.0
        avg_open_price = 0.0
        open_time = None

        close_qty_sum = 0.0
        close_amount_sum = 0.0
        realized_pnl_sum = 0.0
        commission_usdt_sum = 0.0

        closed_positions: List[Dict] = []

        for t in trades:
            qty = float(t["qty"])
            price = float(t["price"])
            realized_pnl = float(t["realizedPnl"])
            commission = float(t.get("commission") or 0.0)
            commission_asset = str(t.get("commissionAsset") or "").upper()
            ts = t["time"]
            trade_side = str(t["side"]).upper()

            if position_side == "LONG":
                if trade_side == "BUY":
                    if abs(position_qty) <= eps:
                        open_time = ts
                        position_qty = qty
                        avg_open_price = price
                        close_qty_sum = 0.0
                        close_amount_sum = 0.0
                        realized_pnl_sum = 0.0
                        commission_usdt_sum = 0.0
                    else:
                        new_qty = position_qty + qty
                        avg_open_price = (position_qty * avg_open_price + qty * price) / new_qty
                        position_qty = new_qty
                    if commission_asset == "USDT":
                        commission_usdt_sum += commission
                elif trade_side == "SELL":
                    qty_closing = min(qty, position_qty)
                    close_qty_sum += qty_closing
                    close_amount_sum += qty_closing * price
                    realized_pnl_sum += realized_pnl
                    if commission_asset == "USDT":
                        commission_usdt_sum += commission
                    position_qty -= qty_closing

                    if abs(position_qty) <= eps:
                        close_price = close_amount_sum / close_qty_sum if close_qty_sum > 0 else 0.0
                        notional = avg_open_price * close_qty_sum
                        net_pnl = realized_pnl_sum - commission_usdt_sum
                        closed_positions.append({
                            "symbol": symbol,
                            "side": "LONG",
                            "qty": round(close_qty_sum, 6),
                            "entry_time": open_time,
                            "close_time": ts,
                            "entry_price": round(avg_open_price, 6),
                            "close_price": round(close_price, 6),
                            "gross_pnl": round(realized_pnl_sum, 6),
                            "commission": round(commission_usdt_sum, 6),
                            "net_pnl": round(net_pnl, 6),
                            "notional": round(notional, 6),
                            "return_pct": round(realized_pnl_sum / notional * 100, 4) if notional else 0,
                            "net_return_pct": round(net_pnl / notional * 100, 4) if notional else 0,
                            "holding_seconds": int((ts - (open_time or ts)) / 1000)
                        })
                        position_qty = 0.0
                        avg_open_price = 0.0
                        open_time = None
                        close_qty_sum = 0.0
                        close_amount_sum = 0.0
                        realized_pnl_sum = 0.0
                        commission_usdt_sum = 0.0

            elif position_side == "SHORT":
                if trade_side == "SELL":
                    if abs(position_qty) <= eps:
                        open_time = ts
                        position_qty = qty
                        avg_open_price = price
                        close_qty_sum = 0.0
                        close_amount_sum = 0.0
                        realized_pnl_sum = 0.0
                        commission_usdt_sum = 0.0
                    else:
                        new_qty = position_qty + qty
                        avg_open_price = (position_qty * avg_open_price + qty * price) / new_qty
                        position_qty = new_qty
                    if commission_asset == "USDT":
                        commission_usdt_sum += commission
                elif trade_side == "BUY":
                    qty_closing = min(qty, position_qty)
                    close_qty_sum += qty_closing
                    close_amount_sum += qty_closing * price
                    realized_pnl_sum += realized_pnl
                    if commission_asset == "USDT":
                        commission_usdt_sum += commission
                    position_qty -= qty_closing

                    if abs(position_qty) <= eps:
                        close_price = close_amount_sum / close_qty_sum if close_qty_sum > 0 else 0.0
                        notional = avg_open_price * close_qty_sum
                        net_pnl = realized_pnl_sum - commission_usdt_sum
                        closed_positions.append({
                            "symbol": symbol,
                            "side": "SHORT",
                            "qty": round(close_qty_sum, 6),
                            "entry_time": open_time,
                            "close_time": ts,
                            "entry_price": round(avg_open_price, 6),
                            "close_price": round(close_price, 6),
                            "gross_pnl": round(realized_pnl_sum, 6),
                            "commission": round(commission_usdt_sum, 6),
                            "net_pnl": round(net_pnl, 6),
                            "notional": round(notional, 6),
                            "return_pct": round(realized_pnl_sum / notional * 100, 4) if notional else 0,
                            "net_return_pct": round(net_pnl / notional * 100, 4) if notional else 0,
                            "holding_seconds": int((ts - (open_time or ts)) / 1000)
                        })
                        position_qty = 0.0
                        avg_open_price = 0.0
                        open_time = None
                        close_qty_sum = 0.0
                        close_amount_sum = 0.0
                        realized_pnl_sum = 0.0
                        commission_usdt_sum = 0.0

        return closed_positions

    @staticmethod
    def _calculate_closed_positions_one_way(trades: List[Dict], symbol: str) -> List[Dict]:
        eps = 1e-12

        position_qty = 0.0
        avg_open_price = 0.0
        open_time = None
        side = None

        close_qty_sum = 0.0
        close_amount_sum = 0.0
        realized_pnl_sum = 0.0
        commission_usdt_sum = 0.0

        closed_positions: List[Dict] = []

        for t in trades:
            qty = float(t["qty"])
            price = float(t["price"])
            realized_pnl = float(t["realizedPnl"])
            commission = float(t.get("commission") or 0.0)
            commission_asset = str(t.get("commissionAsset") or "").upper()
            ts = t["time"]
            trade_side = t["side"]

            if trade_side == "BUY":
                if position_qty < -eps:
                    qty_closing = min(qty, abs(position_qty))
                    close_qty_sum += qty_closing
                    close_amount_sum += qty_closing * price
                    realized_pnl_sum += realized_pnl
                    if commission_asset == "USDT" and qty > 0:
                        commission_usdt_sum += commission * (qty_closing / qty)
                    position_qty += qty_closing

                    if abs(position_qty) <= eps:
                        close_price = close_amount_sum / close_qty_sum if close_qty_sum > 0 else 0.0
                        notional = avg_open_price * close_qty_sum
                        net_pnl = realized_pnl_sum - commission_usdt_sum
                        closed_positions.append({
                            "symbol": symbol,
                            "side": "SHORT",
                            "qty": round(close_qty_sum, 6),
                            "entry_time": open_time,
                            "close_time": ts,
                            "entry_price": round(avg_open_price, 6),
                            "close_price": round(close_price, 6),
                            "gross_pnl": round(realized_pnl_sum, 6),
                            "commission": round(commission_usdt_sum, 6),
                            "net_pnl": round(net_pnl, 6),
                            "notional": round(notional, 6),
                            "return_pct": round(realized_pnl_sum / notional * 100, 4) if notional else 0,
                            "net_return_pct": round(net_pnl / notional * 100, 4) if notional else 0,
                            "holding_seconds": int((ts - (open_time or ts)) / 1000)
                        })
                        avg_open_price = 0.0
                        open_time = None
                        side = None
                        close_qty_sum = 0.0
                        close_amount_sum = 0.0
                        realized_pnl_sum = 0.0
                        commission_usdt_sum = 0.0

                        remaining_qty = qty - qty_closing
                        if remaining_qty > eps:
                            position_qty = remaining_qty
                            avg_open_price = price
                            open_time = ts
                            side = "LONG"
                            if commission_asset == "USDT" and qty > 0:
                                commission_usdt_sum = commission * (remaining_qty / qty)

                else:
                    if abs(position_qty) <= eps:
                        open_time = ts
                        side = "LONG"
                        position_qty = qty
                        avg_open_price = price
                        close_qty_sum = 0.0
                        close_amount_sum = 0.0
                        realized_pnl_sum = 0.0
                        commission_usdt_sum = 0.0
                        if commission_asset == "USDT":
                            commission_usdt_sum += commission
                    else:
                        new_qty = position_qty + qty
                        avg_open_price = (position_qty * avg_open_price + qty * price) / new_qty
                        position_qty = new_qty
                        if commission_asset == "USDT":
                            commission_usdt_sum += commission

            else:
                if position_qty > eps:
                    qty_closing = min(qty, position_qty)
                    close_qty_sum += qty_closing
                    close_amount_sum += qty_closing * price
                    realized_pnl_sum += realized_pnl
                    if commission_asset == "USDT" and qty > 0:
                        commission_usdt_sum += commission * (qty_closing / qty)
                    position_qty -= qty_closing

                    if abs(position_qty) <= eps:
                        close_price = close_amount_sum / close_qty_sum if close_qty_sum > 0 else 0.0
                        notional = avg_open_price * close_qty_sum
                        net_pnl = realized_pnl_sum - commission_usdt_sum
                        closed_positions.append({
                            "symbol": symbol,
                            "side": "LONG",
                            "qty": round(close_qty_sum, 6),
                            "entry_time": open_time,
                            "close_time": ts,
                            "entry_price": round(avg_open_price, 6),
                            "close_price": round(close_price, 6),
                            "gross_pnl": round(realized_pnl_sum, 6),
                            "commission": round(commission_usdt_sum, 6),
                            "net_pnl": round(net_pnl, 6),
                            "notional": round(notional, 6),
                            "return_pct": round(realized_pnl_sum / notional * 100, 4) if notional else 0,
                            "net_return_pct": round(net_pnl / notional * 100, 4) if notional else 0,
                            "holding_seconds": int((ts - (open_time or ts)) / 1000)
                        })
                        avg_open_price = 0.0
                        open_time = None
                        side = None
                        close_qty_sum = 0.0
                        close_amount_sum = 0.0
                        realized_pnl_sum = 0.0
                        commission_usdt_sum = 0.0

                        remaining_qty = qty - qty_closing
                        if remaining_qty > eps:
                            position_qty = -remaining_qty
                            avg_open_price = price
                            open_time = ts
                            side = "SHORT"
                            if commission_asset == "USDT" and qty > 0:
                                commission_usdt_sum = commission * (remaining_qty / qty)

                else:
                    if abs(position_qty) <= eps:
                        open_time = ts
                        side = "SHORT"
                        position_qty = -qty
                        avg_open_price = price
                        close_qty_sum = 0.0
                        close_amount_sum = 0.0
                        realized_pnl_sum = 0.0
                        commission_usdt_sum = 0.0
                        if commission_asset == "USDT":
                            commission_usdt_sum += commission
                    else:
                        current_abs_qty = abs(position_qty)
                        new_abs_qty = current_abs_qty + qty
                        avg_open_price = (current_abs_qty * avg_open_price + qty * price) / new_abs_qty
                        position_qty -= qty
                        if commission_asset == "USDT":
                            commission_usdt_sum += commission

        return closed_positions


if __name__ == "__main__":
    import os
    import dotenv
    
    dotenv.load_dotenv()

    API_KEY = str(os.getenv("BINANCE_API_KEY", "") or "").strip()
    API_SECRET = str(os.getenv("BINANCE_API_SECRET", "") or "").strip()
    if not API_KEY or not API_SECRET:
        raise RuntimeError("缺少 BINANCE_API_KEY / BINANCE_API_SECRET")

    symbol = "RIVERUSDT"

    try:
        client = BinanceFuturesClient(API_KEY, API_SECRET)
        print(f"Fetching trades for {symbol}...")
        trades = client.get_user_trades(symbol)
        print(trades)

        print(f"Fetched {len(trades)} trades.")

        last = client.get_last_position(trades)
        print(last)

        # position_history = client.rebuild_position_history(trades)
        # print("Position History Sample:")
        # for h in position_history[-5:]:
        #     print(h)

        print("\nCalculating Closed Positions:")
        closed_positions = client.calculate_closed_positions(trades, symbol)

        if closed_positions:
            df = pd.DataFrame(closed_positions)
            pd.set_option("display.max_columns", None)
            print(df)
            print(closed_positions)
        else:
            print("No closed positions found.")

    except Exception as e:
        print(f"Error: {e}")
