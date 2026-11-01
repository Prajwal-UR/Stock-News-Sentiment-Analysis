from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from stockq.indicators import annualized_volatility, calculate_indicators, maximum_drawdown


@dataclass(frozen=True)
class StockComparison:
    common_dates: pd.DatetimeIndex
    normalized_prices: dict[str, pd.Series]
    metrics: list[dict[str, float | str]]


def compare_histories(histories: dict[str, pd.DataFrame]) -> StockComparison:
    if not 2 <= len(histories) <= 3:
        raise ValueError("Provide two or three stock histories for comparison.")
    common_dates: pd.DatetimeIndex | None = None
    for history in histories.values():
        dates = history.index[history["Close"].notna()]
        common_dates = dates if common_dates is None else common_dates.intersection(dates)
    if common_dates is None or len(common_dates) < 2:
        raise ValueError("Stocks do not have at least two common trading observations.")
    common_dates = common_dates.sort_values()

    normalized: dict[str, pd.Series] = {}
    metrics: list[dict[str, float | str]] = []
    for symbol, history in histories.items():
        aligned = history.loc[common_dates]
        close = aligned["Close"]
        technical = calculate_indicators(aligned)
        sma50 = technical["SMA 50"].iloc[-1]
        rsi = technical["RSI 14"].iloc[-1]
        normalized[symbol] = close / close.iloc[0] * 100
        metrics.append({
            "Symbol": symbol,
            "Common-period return": float(close.iloc[-1] / close.iloc[0] - 1),
            "Annualized volatility": annualized_volatility(close),
            "Maximum drawdown": maximum_drawdown(close),
            "Close vs SMA 50": float(close.iloc[-1] / sma50 - 1) if pd.notna(sma50) else float("nan"),
            "RSI 14": float(rsi) if pd.notna(rsi) else float("nan"),
        })
    return StockComparison(common_dates, normalized, metrics)
