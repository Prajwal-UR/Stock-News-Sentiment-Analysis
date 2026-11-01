from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from typing import Callable, Protocol

import pandas as pd

from stockq.config import Stock, cache_ttl_seconds, request_timeout_seconds

logger = logging.getLogger(__name__)
REQUIRED_COLUMNS = ("Open", "High", "Low", "Close", "Volume")


class MarketDataError(RuntimeError):
    """An explicit provider or validation error; no sample values are substituted."""


@dataclass(frozen=True)
class MarketData:
    stock: Stock
    history: pd.DataFrame
    fundamentals: dict[str, object]
    fetched_at: pd.Timestamp
    cache_status: str


class MarketDataProvider(Protocol):
    def get_history(self, stock: Stock, period: str) -> MarketData: ...


def validate_history(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        raise MarketDataError("The provider returned no historical prices for this symbol and period.")

    result = frame.copy()
    if isinstance(result.columns, pd.MultiIndex):
        result.columns = result.columns.get_level_values(0)
    missing = [column for column in REQUIRED_COLUMNS if column not in result.columns]
    if missing:
        raise MarketDataError(f"Provider data is missing required fields: {', '.join(missing)}.")

    result = result.loc[:, REQUIRED_COLUMNS]
    for column in REQUIRED_COLUMNS:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result = result.dropna(subset=list(REQUIRED_COLUMNS)).sort_index()
    result = result[~result.index.duplicated(keep="last")]
    result = result[
        (result[["Open", "High", "Low", "Close"]] > 0).all(axis=1)
        & (result["High"] >= result["Low"])
        & (result["Volume"] >= 0)
    ]
    if result.empty:
        raise MarketDataError("No valid OHLCV observations remain after validating provider data.")
    if not isinstance(result.index, pd.DatetimeIndex):
        raise MarketDataError("Provider dates are not valid timestamps.")
    return result


class YFinanceProvider:
    def __init__(
        self,
        ttl_seconds: int | None = None,
        timeout_seconds: int | None = None,
        downloader: Callable[..., pd.DataFrame] | None = None,
    ) -> None:
        self.ttl_seconds = cache_ttl_seconds() if ttl_seconds is None else ttl_seconds
        self.timeout_seconds = request_timeout_seconds() if timeout_seconds is None else timeout_seconds
        self._downloader = downloader
        self._cache: dict[tuple[str, str], tuple[float, MarketData]] = {}
        self._lock = threading.Lock()

    def get_history(self, stock: Stock, period: str) -> MarketData:
        if not re.fullmatch(r"(?:1mo|3mo|6mo|1y|5y|max)", period):
            raise MarketDataError("Unsupported historical period.")
        key = (stock.symbol, period)
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(key)
            if cached and now - cached[0] < self.ttl_seconds:
                data = cached[1]
                return MarketData(data.stock, data.history.copy(), data.fundamentals,
                                  data.fetched_at, "cached")

        try:
            download = self._downloader
            if download is None:
                import yfinance as yf

                download = yf.download
            frame = download(
                stock.symbol,
                period=period,
                interval="1d",
                auto_adjust=True,
                progress=False,
                threads=False,
                timeout=self.timeout_seconds,
            )
        except Exception as exc:
            raise MarketDataError(f"Could not retrieve market data: {exc}") from exc

        history = validate_history(frame)
        fundamentals: dict[str, object] = {}
        try:
            if self._downloader is None:
                import yfinance as yf

                fundamentals = yf.Ticker(stock.symbol).get_info()
        except Exception as exc:
            logger.warning("Fundamentals unavailable for %s: %s", stock.symbol, exc)

        result = MarketData(
            stock=stock,
            history=history,
            fundamentals=fundamentals,
            fetched_at=pd.Timestamp.now(tz="UTC"),
            cache_status="provider",
        )
        with self._lock:
            self._cache[key] = (time.monotonic(), result)
        return MarketData(stock, history.copy(), fundamentals, result.fetched_at, "provider")
