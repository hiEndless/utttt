from data_server.binance.ws_binance.utils.reids_connect import RedisClient

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
                    filtered.append(p)
        return filtered

    def get_old_data(self):
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
        # print("新增：", added_items)
        return added_items

    def find_removed_items(self, old_data, new_data):
        new_set = set((x.get('symbol'), x.get('isolatedMargin'), x.get('positionSide')) for x in new_data)
        removed_items = [
            i for i in old_data
            if (i.get('symbol'), i.get('isolatedMargin'), i.get('positionSide')) not in new_set
        ]
        # print("移除：", removed_items)
        return removed_items

    def analysis(self, new_data):
        new_data = self.data_clean(new_data)
        old_data = self.get_old_data()

        if old_data is None:
            self.set_old_data(new_data)
            return

        if new_data != old_data:
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
        return


if __name__ == "__main__":
    new_data = []
    old_data = [{'symbol': '1000PEPEUSDT', 'positionSide': 'LONG', 'positionAmt': '852', 'unrealizedProfit': '0.00930384', 'isolatedMargin': '0', 'notional': '5.01923424', 'isolatedWallet': '0', 'initialMargin': '0.50192343', 'maintMargin': '0.03262502', 'updateTime': 1763031017638}]
    obj = BinanceAnalysisService()
    obj.find_removed_items(old_data, new_data)
    obj.find_added_items(old_data, new_data)