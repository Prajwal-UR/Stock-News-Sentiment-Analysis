from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from server import app


class WebsiteApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_home_serves_webpage(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("StockQ", response.text)
        self.assertIn("/static/app.js", response.text)

    def test_health_and_stock_search_catalog(self):
        self.assertEqual(self.client.get("/api/health").json(), {"status": "ok"})
        response = self.client.get("/api/stocks")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(stock["symbol"] == "RELIANCE.NS" for stock in response.json()))

    def test_analysis_validates_symbol_before_network_access(self):
        response = self.client.get("/api/analysis", params={"symbol": "RELIANCE;DROP"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid symbol", response.json()["detail"])

    def test_compare_requires_two_or_three_symbols(self):
        response = self.client.post("/api/compare", json={
            "symbols": ["RELIANCE"], "exchange": "NSE", "period": "1y",
        })
        self.assertEqual(response.status_code, 422)

    def test_compare_rejects_duplicate_symbols_without_network_access(self):
        response = self.client.post("/api/compare", json={
            "symbols": ["RELIANCE", "RELIANCE.NS"], "exchange": "NSE", "period": "1y",
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("distinct", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
