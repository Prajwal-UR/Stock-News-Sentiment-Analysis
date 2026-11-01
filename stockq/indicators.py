from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def calculate_indicators(history: pd.DataFrame) -> pd.DataFrame:
    required = {"High", "Low", "Close", "Volume"}
    missing = required.difference(history.columns)
    if missing:
        raise ValueError(f"Missing required OHLCV columns: {', '.join(sorted(missing))}")
    close = pd.to_numeric(history["Close"], errors="coerce")
    high = pd.to_numeric(history["High"], errors="coerce")
    low = pd.to_numeric(history["Low"], errors="coerce")
    volume = pd.to_numeric(history["Volume"], errors="coerce")
    output = history.copy()

    for window in (20, 50, 200):
        output[f"SMA {window}"] = close.rolling(window, min_periods=window).mean()
    output["EMA 12"] = close.ewm(span=12, adjust=False, min_periods=12).mean()
    output["EMA 26"] = close.ewm(span=26, adjust=False, min_periods=26).mean()
    change = close.diff()
    gain = change.clip(lower=0)
    loss = -change.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    relative_strength = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + relative_strength))
    output["RSI 14"] = rsi.mask((avg_loss == 0) & (avg_gain > 0), 100)

    output["MACD"] = output["EMA 12"] - output["EMA 26"]
    output["MACD signal"] = output["MACD"].ewm(span=9, adjust=False, min_periods=9).mean()
    output["MACD histogram"] = output["MACD"] - output["MACD signal"]
    mid = close.rolling(20, min_periods=20).mean()
    deviation = close.rolling(20, min_periods=20).std(ddof=0)
    output["Bollinger middle"] = mid
    output["Bollinger upper"] = mid + 2 * deviation
    output["Bollinger lower"] = mid - 2 * deviation

    previous_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - previous_close).abs(), (low - previous_close).abs()], axis=1
    ).max(axis=1)
    output["ATR 14"] = true_range.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    output["Volume MA 20"] = volume.rolling(20, min_periods=20).mean()
    output["Daily return"] = close.pct_change(fill_method=None)
    output["Cumulative return"] = (1 + output["Daily return"].fillna(0)).cumprod() - 1
    output["Drawdown"] = close / close.cummax() - 1
    output["Annualized volatility 20"] = (
        output["Daily return"].rolling(20, min_periods=20).std(ddof=1) * np.sqrt(TRADING_DAYS)
    )
    return output


def maximum_drawdown(close: pd.Series) -> float:
    values = pd.to_numeric(close, errors="coerce").dropna()
    if values.empty:
        return float("nan")
    return float((values / values.cummax() - 1).min())


def annualized_volatility(close: pd.Series) -> float:
    returns = pd.to_numeric(close, errors="coerce").pct_change(fill_method=None).dropna()
    if len(returns) < 2:
        return float("nan")
    return float(returns.std(ddof=1) * np.sqrt(TRADING_DAYS))
