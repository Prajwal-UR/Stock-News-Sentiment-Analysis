from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from stockq.config import resolve_symbol
from stockq.comparison import compare_histories
from stockq.forecasting import forecast_close
from stockq.fundamentals import extract_fundamentals
from stockq.indicators import calculate_indicators, maximum_drawdown
from stockq.market_data import MarketDataError, YFinanceProvider, validate_history
from stockq.persistence import JsonWatchlistStore
from stockq.risk import assess_risk, classify_volatility


def sample_history(count: int = 260) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-01", periods=count)
    close = pd.Series(np.arange(count, dtype=float) + 100, index=dates)
    return pd.DataFrame({
        "Open": close - 0.5, "High": close + 1, "Low": close - 1,
        "Close": close, "Volume": 1000 + np.arange(count),
    }, index=dates)


class AnalyticsTests(unittest.TestCase):
    def test_return_and_drawdown_are_calculated_from_observations(self):
        history = sample_history(3)
        history["Close"] = [100, 120, 90]
        output = calculate_indicators(history)
        self.assertAlmostEqual(output["Daily return"].iloc[1], 0.2)
        self.assertAlmostEqual(output["Cumulative return"].iloc[-1], -0.1)
        self.assertAlmostEqual(maximum_drawdown(history["Close"]), -0.25)

    def test_moving_average_rsi_macd_and_bollinger_warmups(self):
        history = sample_history(220)
        output = calculate_indicators(history)
        self.assertTrue(pd.isna(output["SMA 20"].iloc[18]))
        self.assertAlmostEqual(output["SMA 20"].iloc[19], history["Close"].iloc[:20].mean())
        self.assertAlmostEqual(output["RSI 14"].iloc[-1], 100)
        self.assertTrue(pd.notna(output["MACD signal"].iloc[-1]))
        self.assertAlmostEqual(output["Bollinger middle"].iloc[-1], history["Close"].tail(20).mean())

    def test_risk_thresholds_are_explicit(self):
        history = sample_history(80)
        indicators = calculate_indicators(history)
        assessment = assess_risk(history, indicators)
        self.assertIn(assessment.classification, {"Low", "Moderate", "High"})
        self.assertIn("20%-<40%", assessment.thresholds)

    def test_risk_classification_boundaries(self):
        self.assertEqual(classify_volatility(0.1999), "Low")
        self.assertEqual(classify_volatility(0.20), "Moderate")
        self.assertEqual(classify_volatility(0.3999), "Moderate")
        self.assertEqual(classify_volatility(0.40), "High")
        self.assertEqual(classify_volatility(float("nan")), "Insufficient history")

    def test_invalid_symbol_and_invalid_provider_rows_are_rejected(self):
        with self.assertRaises(ValueError):
            resolve_symbol("RELIANCE;DROP")
        with self.assertRaises(MarketDataError):
            validate_history(pd.DataFrame())

    def test_provider_failure_is_not_replaced_with_sample_data(self):
        def fail(*args, **kwargs):
            raise TimeoutError("provider timeout")
        provider = YFinanceProvider(downloader=fail)
        with self.assertRaisesRegex(MarketDataError, "provider timeout"):
            provider.get_history(resolve_symbol("RELIANCE"), "1y")

    def test_provider_validates_and_marks_cache(self):
        calls = []
        frame = sample_history(5)
        def download(*args, **kwargs):
            calls.append(1)
            return frame
        provider = YFinanceProvider(ttl_seconds=60, downloader=download)
        stock = resolve_symbol("RELIANCE")
        first = provider.get_history(stock, "1y")
        second = provider.get_history(stock, "1y")
        self.assertEqual(first.cache_status, "provider")
        self.assertEqual(second.cache_status, "cached")
        self.assertEqual(len(calls), 1)

    def test_forecast_uses_chronological_splits_and_reports_baselines(self):
        history = sample_history(300)
        result = forecast_close(history["Close"], 5)
        self.assertLess(result.train_end, result.validation_start)
        self.assertLess(result.validation_end, result.test_start)
        self.assertLess(result.train_end + pd.offsets.BDay(5), result.validation_start)
        self.assertLess(result.validation_end + pd.offsets.BDay(5), result.test_start)
        self.assertEqual(result.test_metrics["Persistence"]["MAE"], 5.0)
        self.assertIn("Random Forest", result.test_metrics)

    def test_forecast_requires_minimum_history(self):
        with self.assertRaisesRegex(ValueError, "At least 80"):
            forecast_close(sample_history(40)["Close"])

    def test_unavailable_fundamentals_are_not_invented(self):
        metrics = extract_fundamentals({"mostRecentQuarter": 1_760_000_000})
        self.assertTrue(all(metric.value is None for metric in metrics))
        self.assertTrue(all(metric.source for metric in metrics))
        self.assertTrue(all(metric.reporting_period == "2025-10-09" for metric in metrics))

    def test_dividend_yield_percentage_points_are_normalized(self):
        metrics = extract_fundamentals({"dividendYield": 1.9})
        yield_metric = next(metric for metric in metrics if metric.label == "Dividend yield")
        self.assertAlmostEqual(yield_metric.value, 0.019)

    def test_comparison_uses_common_dates_and_normalized_prices(self):
        first = sample_history(60)
        second = sample_history(55)
        second["Close"] = second["Close"] * 2
        result = compare_histories({"A": first, "B": second})
        self.assertEqual(len(result.common_dates), 55)
        self.assertEqual(result.normalized_prices["A"].iloc[0], 100)
        self.assertEqual(result.normalized_prices["B"].iloc[0], 100)
        self.assertEqual(len(result.metrics), 2)

    def test_watchlist_add_remove_and_settings_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            store = JsonWatchlistStore(Path(directory) / "watchlist.json")
            store.add("RELIANCE.NS", "1y", 5)
            store.add("RELIANCE.NS", "5y", 20)
            self.assertEqual(store.list_items(), [{"symbol": "RELIANCE.NS", "period": "5y", "horizon": 20}])
            store.remove("RELIANCE.NS")
            self.assertEqual(store.list_items(), [])


if __name__ == "__main__":
    unittest.main()
