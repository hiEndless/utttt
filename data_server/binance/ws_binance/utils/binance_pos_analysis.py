from data_server.binance.ws_binance.utils.reids_connect import RedisClient
import uuid

previous_data = None


class BinanceAnalysisService:
    def __init__(self):
        self.redis_client = RedisClient()

    def data_clean(self, new_data):
        filtered = []
        if isinstance(new_data, list):
            for p in new_data:
                try:
                    amt = float(str(p.get("positionAmt", "0")))
                except Exception:
                    amt = 0.0
                if amt != 0.0:
                    if p.get("positionSide") == "BOTH":
                        if amt > 0:
                            p["positionSide"] = "LONG"
                        else:
                            p["positionSide"] = "SHORT"
                    filtered.append(p)
        return filtered

    def add_pnl_ratio(self, positions):
        if isinstance(positions, list):
            for p in positions:
                try:
                    up = float(str(p.get('unRealizedProfit', '0')))
                except Exception:
                    up = 0.0
                try:
                    im = float(str(p.get('initialMargin', '0')))
                except Exception:
                    im = 0.0
                ratio = 0.0 if im == 0.0 else (up / im)
                p['pnl_ratio'] = ratio
        return positions

    def apply_trade_ids(self, old_data, new_data):
        old_iter = old_data if isinstance(old_data, list) else []
        old_index = {(i.get('symbol'), i.get('positionSide')): i.get('trade_id') for i in old_iter}
        if isinstance(new_data, list):
            for p in new_data:
                key = (p.get('symbol'), p.get('positionSide'))
                tid = old_index.get(key)
                if not tid:
                    tid = uuid.uuid4().hex
                p['trade_id'] = tid
        return new_data

    def get_old_data(self):
        global previous_data
        if previous_data is None:
            cached = self.redis_client.get_json("positions:binance")
            if cached is not None:
                previous_data = cached
        return previous_data

    def set_old_data(self, new_data):
        global previous_data
        previous_data = new_data

    def find_added_items(self, old_data, new_data):
        old_set = set((i.get('symbol'), i.get('isolatedMargin'), i.get('positionSide')) for i in old_data)
        added_items = [
            x for x in new_data
            if (x.get('symbol'), x.get('isolatedMargin'), x.get('positionSide')) not in old_set
        ]
        print("新增：", added_items)
        return added_items

    def find_removed_items(self, old_data, new_data):
        new_set = set((x.get('symbol'), x.get('isolatedMargin'), x.get('positionSide')) for x in new_data)
        removed_items = [
            i for i in old_data
            if (i.get('symbol'), i.get('isolatedMargin'), i.get('positionSide')) not in new_set
        ]
        print("移除：", removed_items)
        return removed_items

    def find_changed_items(self, old_data, new_data):
        old_map = {}
        for i in old_data:
            key = (i.get('symbol'), i.get('positionSide'))
            old_map[key] = i

        results = []
        for j in new_data:
            key = (j.get('symbol'), j.get('positionSide'))
            if key in old_map:
                i = old_map[key]
                try:
                    old_amt = float(str(i.get('positionAmt', '0')))
                    old_pnl_ratio = float(str(i.get('pnl_ratio', '0')))
                except Exception:
                    old_amt = 0.0
                    old_pnl_ratio = 0.0
                try:
                    new_amt = float(str(j.get('positionAmt', '0')))
                    new_pnl_ratio = float(str(j.get('pnl_ratio', '0')))
                except Exception:
                    new_amt = 0.0
                    new_pnl_ratio = 0.0
                if old_amt != new_amt:
                    change = 'increase' if abs(new_amt) > abs(old_amt) else 'decrease'
                    results.append({
                        'symbol': j.get('symbol'),
                        'side': j.get('positionSide'),
                        'old_position_amt': old_amt,
                        'new_position_amt': new_amt,
                        'old_pnl_ratio': old_pnl_ratio,
                        'new_pnl_ratio': new_pnl_ratio,
                        'trade_id': j.get('trade_id'),
                        'change': change
                    })
        print("修改：", results)
        return results

    def analysis(self, new_data):
        new_data = self.data_clean(new_data)
        new_data = self.add_pnl_ratio(new_data)
        old_data = self.get_old_data()

        if old_data is None:
            new_data = self.apply_trade_ids([], new_data)
            self.set_old_data(new_data)
            self.redis_client.set_json("positions:binance", new_data)
            return

        if new_data != old_data:
            new_data = self.apply_trade_ids(old_data, new_data)
            self.set_old_data(new_data)
            self.redis_client.set_json("positions:binance", new_data)

            added_items = self.find_added_items(old_data, new_data)
            if added_items:
                for item in added_items:
                    self.redis_client.conn.sadd("symbol:binance", f"{item.get('symbol')}")

            removed_items = self.find_removed_items(old_data, new_data)
            if removed_items:
                for item in removed_items:
                    self.redis_client.conn.srem("symbol:binance", f"{item.get('symbol')}")
                    print("存入数据库：", item)

            changed_items = self.find_changed_items(old_data, new_data)
            if changed_items:
                for item in changed_items:
                    print("变化的数据：", item)
        return


if __name__ == "__main__":
    # old_data = []
    old_data = [
        {'symbol': '1000PEPEUSDT', 'positionSide': 'LONG', 'positionAmt': '851', 'unrealizedProfit': '0.00930384',
         'isolatedMargin': '0', 'notional': '5.01923424', 'isolatedWallet': '0', 'initialMargin': '0.50192343',
         'maintMargin': '0.03262502', 'updateTime': 1763031017638, 'trade_id': '2e317d6f9ace4114a4c44624eff952f5'}]
    new_data = [
        {'symbol': '1000PEPEUSDT', 'positionSide': 'LONG', 'positionAmt': '852', 'unrealizedProfit': '0.00930384',
         'isolatedMargin': '0', 'notional': '5.01923424', 'isolatedWallet': '0', 'initialMargin': '0.50192343',
         'maintMargin': '0.03262502', 'updateTime': 1763031017638},
        {'symbol': '1000PEPEUSDT', 'positionSide': 'SHORT', 'positionAmt': '852', 'unrealizedProfit': '0.00930384',
         'isolatedMargin': '0', 'notional': '5.01923424', 'isolatedWallet': '0', 'initialMargin': '0.50192343',
         'maintMargin': '0.03262502', 'updateTime': 1763031017638},
    ]
    obj = BinanceAnalysisService()
    obj.set_old_data(old_data)
    obj.analysis(new_data)
    # obj.find_removed_items(old_data, new_data)
    # obj.find_added_items(old_data, new_data)
    # obj.find_changed_items(old_data, new_data)
