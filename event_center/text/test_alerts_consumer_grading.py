import unittest

from event_center.alerts_consumer import grade_alert


class TestAlertsConsumerGrading(unittest.TestCase):
    def test_pct_change_grading(self):
        self.assertEqual(grade_alert("pct_change_up", {"pct": 0.0009}), 1)
        self.assertEqual(grade_alert("pct_change_down", {"pct": 0.012}), 2)
        self.assertEqual(grade_alert("pct_change_up", {"pct": 0.025}), 3)
        self.assertEqual(grade_alert("pct_change_down", {"pct": 0.051}), 4)

    def test_zscore_grading(self):
        self.assertEqual(grade_alert("zscore_spike", {"z": 4.9}), 1)
        self.assertEqual(grade_alert("zscore_spike", {"z": 5.1}), 2)
        self.assertEqual(grade_alert("zscore_spike", {"z": 8.0}), 3)
        self.assertEqual(grade_alert("zscore_spike", {"z": 12.0}), 4)

    def test_depth_collapse_grading(self):
        self.assertEqual(grade_alert("bid_collapse", {"ratio": 0.35, "streak": 1}), 1)
        self.assertEqual(grade_alert("ask_collapse", {"ratio": 0.25, "streak": 1}), 2)
        self.assertEqual(grade_alert("bid_collapse", {"ratio": 0.18, "streak": 2}), 3)
        self.assertEqual(grade_alert("ask_collapse", {"ratio": 0.09, "streak": 3}), 4)

    def test_liquidity_collapse_grading(self):
        self.assertEqual(grade_alert("liquidity_collapse", {"ratio": [0.3, 0.28], "count": 2}), 2)
        self.assertEqual(grade_alert("liquidity_collapse", {"ratio": [0.24, 0.26], "count": 2}), 3)
        self.assertEqual(grade_alert("liquidity_collapse", {"ratio": [0.14, 0.2], "count": 2}), 4)

    def test_one_side_grading(self):
        self.assertEqual(grade_alert("one_side_up", {"pct": 0.009, "count": 2}), 1)
        self.assertEqual(grade_alert("one_side_down", {"pct": 0.012, "count": 3}), 2)
        self.assertEqual(grade_alert("one_side_up", {"pct": 0.031, "count": 5}), 3)
        self.assertEqual(grade_alert("one_side_down", {"pct": 0.052, "count": 10}), 4)


if __name__ == "__main__":
    unittest.main()
