import unittest
from event_center.alerts_consumer import AlertsConsumer


class TestAlertsConsumerDedup(unittest.TestCase):
    def setUp(self):
        self.ac = AlertsConsumer()
        self.ac.emit_min_interval_ms = 2000
        self.ac.dedup_window_ms = 3000

    def test_same_payload_within_window(self):
        symbol = "BTCUSDT"
        atype = "price.pct_up"
        details = {"pct": 0.025, "p0": 100, "pN": 102.5}
        ts1 = 100000
        ts2 = ts1 + 1500
        self.assertTrue(self.ac._should_emit(symbol, atype, ts1, details))
        self.ac._last_emit_ts[(symbol, atype)] = ts1
        self.ac._last_payload_fp[(symbol, atype)] = self.ac._fingerprint(details)
        self.assertFalse(self.ac._should_emit(symbol, atype, ts2, details))

    def test_different_payload_within_window(self):
        symbol = "BTCUSDT"
        atype = "price.pct_up"
        d1 = {"pct": 0.025, "p0": 100, "pN": 102.5}
        d2 = {"pct": 0.030, "p0": 100, "pN": 103.0}
        ts1 = 200000
        ts2 = ts1 + 1500
        self.assertTrue(self.ac._should_emit(symbol, atype, ts1, d1))
        self.ac._last_emit_ts[(symbol, atype)] = ts1
        self.ac._last_payload_fp[(symbol, atype)] = self.ac._fingerprint(d1)
        self.assertTrue(self.ac._should_emit(symbol, atype, ts2, d2))


if __name__ == "__main__":
    unittest.main()