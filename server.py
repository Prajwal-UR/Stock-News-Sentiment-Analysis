from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from stockq.comparison import compare_histories
from stockq.config import EXAMPLE_STOCKS, PERIODS, resolve_symbol
from stockq.forecasting import forecast_close
from stockq.fundamentals import extract_fundamentals
from stockq.indicators import calculate_indicators
from stockq.market_data import MarketDataError, YFinanceProvider
from stockq.persistence import JsonWatchlistStore
from stockq.research import build_research_summary
from stockq.risk import assess_risk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent
provider = YFinanceProvider()
watchlist = JsonWatchlistStore()

app = FastAPI(title="StockQ API", version="1.0.0")
app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")


class CompareRequest(BaseModel):
    symbols: list[str] = Field(min_length=2, max_length=3)
    exchange: str = Field(default="NSE", pattern="^(NSE|BSE)$")
    period: str = Field(default="1y", pattern="^(1mo|3mo|6mo|1y|5y|max)$")


class WatchlistEntry(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    period: str = Field(default="1y", pattern="^(1mo|3mo|6mo|1y|5y|max)$")
    horizon: Literal[1, 5, 20] = 5


def number(value: Any) -> float | None:
    if value is None or isinstance(value, (bool, np.bool_)) or not pd.notna(value):
        return None
    return float(value)


def analysis_for(query: str, exchange: str, period: str, horizon: int) -> dict[str, Any]:
    stock = resolve_symbol(query, exchange)
    market = provider.get_history(stock, period)
    history = market.history
    indicators = calculate_indicators(history)
    risk = assess_risk(history, indicators)
    latest = history.iloc[-1]
    previous_close = number(history["Close"].iloc[-2]) if len(history) > 1 else None
    latest_close = number(latest["Close"])
    change = latest_close - previous_close if latest_close is not None and previous_close else None
    change_pct = change / previous_close if change is not None and previous_close else None
    has_52_weeks = history.index[-1] - history.index[0] >= pd.Timedelta(days=364)
    high_52 = history["High"].tail(252).max() if has_52_weeks else None
    low_52 = history["Low"].tail(252).min() if has_52_weeks else None

    indicator_columns = [
        "SMA 20", "SMA 50", "SMA 200", "EMA 12", "EMA 26", "RSI 14", "MACD",
        "MACD signal", "MACD histogram", "Bollinger upper", "Bollinger middle",
        "Bollinger lower", "ATR 14", "Volume MA 20", "Daily return",
        "Cumulative return", "Drawdown", "Annualized volatility 20",
    ]
    rows = []
    for timestamp, row in indicators.iterrows():
        rows.append({
            "date": pd.Timestamp(timestamp).date().isoformat(),
            **{column: number(row[column]) for column in ("Open", "High", "Low", "Close", "Volume")},
            **{column: number(row[column]) for column in indicator_columns},
        })

    forecast: dict[str, Any] | None = None
    forecast_error: str | None = None
    try:
        result = forecast_close(history["Close"], horizon)
        forecast = {
            "horizon": result.horizon,
            "target_date": result.target_date.date().isoformat(),
            "estimate": result.estimate,
            "persistence": result.baseline_persistence,
            "moving_average": result.baseline_moving_average,
            "train": [result.train_start.date().isoformat(), result.train_end.date().isoformat()],
            "validation": [
                result.validation_start.date().isoformat(), result.validation_end.date().isoformat()
            ],
            "test": [result.test_start.date().isoformat(), result.test_end.date().isoformat()],
            "validation_metrics": result.validation_metrics,
            "test_metrics": result.test_metrics,
            "validation_observations": result.validation_observations,
            "test_observations": result.test_observations,
        }
    except ValueError as exc:
        forecast_error = str(exc)

    summary = build_research_summary(
        stock.symbol, history, indicators, risk, market.fundamentals
    )
    fundamentals = [
        {
            "label": item.label,
            "value": number(item.value),
            "source": item.source,
            "currency": item.currency,
            "period": item.reporting_period,
        }
        for item in extract_fundamentals(market.fundamentals)
    ]
    return {
        "stock": {
            "symbol": stock.symbol,
            "name": stock.name,
            "exchange": stock.exchange,
            "currency": stock.currency,
        },
        "period": period,
        "fetched_at": market.fetched_at.isoformat(),
        "latest_session": pd.Timestamp(history.index[-1]).date().isoformat(),
        "cache_status": market.cache_status,
        "overview": {
            "close": latest_close,
            "change": change,
            "change_pct": change_pct,
            "period_high": number(history["High"].max()),
            "period_low": number(history["Low"].min()),
            "high_52": number(high_52),
            "low_52": number(low_52),
            "volume": number(latest["Volume"]),
            "volume_ma": number(indicators["Volume MA 20"].iloc[-1]),
            "period_return": number(latest_close / number(history["Close"].iloc[0]) - 1),
        },
        "risk": {
            "volatility": number(risk.annualized_volatility),
            "drawdown": number(risk.maximum_drawdown),
            "recent_return": number(risk.recent_20_session_return),
            "atr_pct": number(risk.atr_percent),
            "classification": risk.classification,
            "thresholds": risk.thresholds,
        },
        "fundamentals": fundamentals,
        "history": rows,
        "forecast": forecast,
        "forecast_error": forecast_error,
        "research": summary,
        "period_options": PERIODS,
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "web" / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/stocks")
def stocks() -> list[dict[str, str]]:
    return [
        {"symbol": stock.symbol, "name": stock.name, "exchange": stock.exchange}
        for stock in EXAMPLE_STOCKS
    ]


@app.get("/api/analysis")
def analysis(
    symbol: str = Query(default="RELIANCE", min_length=1, max_length=40),
    exchange: str = Query(default="NSE", pattern="^(NSE|BSE)$"),
    period: str = Query(default="1y", pattern="^(1mo|3mo|6mo|1y|5y|max)$"),
    horizon: int = Query(default=5, ge=1, le=20),
) -> dict[str, Any]:
    try:
        return analysis_for(symbol, exchange, period, horizon)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected analysis failure for %s", symbol)
        raise HTTPException(status_code=500, detail="Unexpected analysis error; see server logs.") from exc


@app.post("/api/compare")
def compare(request: CompareRequest) -> dict[str, Any]:
    try:
        stocks_and_history: dict[str, Any] = {}
        fundamentals: dict[str, list[dict[str, Any]]] = {}
        for symbol in request.symbols:
            stock = resolve_symbol(symbol, request.exchange)
            if stock.symbol in stocks_and_history:
                raise ValueError("Comparison symbols must be distinct.")
            market = provider.get_history(stock, request.period)
            stocks_and_history[stock.symbol] = market.history
            fundamentals[stock.symbol] = [
                {
                    "label": item.label,
                    "value": number(item.value),
                    "currency": item.currency,
                }
                for item in extract_fundamentals(market.fundamentals)
            ]
        result = compare_histories(stocks_and_history)
        return {
            "dates": [timestamp.date().isoformat() for timestamp in result.common_dates],
            "metrics": result.metrics,
            "normalized": {
                symbol: [number(value) for value in series]
                for symbol, series in result.normalized_prices.items()
            },
            "fundamentals": fundamentals,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/watchlist")
def get_watchlist() -> list[dict[str, object]]:
    try:
        return watchlist.list_items()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/watchlist")
def add_watchlist(entry: WatchlistEntry) -> list[dict[str, object]]:
    try:
        stock = resolve_symbol(entry.symbol)
        watchlist.add(stock.symbol, entry.period, entry.horizon)
        return watchlist.list_items()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete("/api/watchlist/{symbol}")
def remove_watchlist(symbol: str) -> list[dict[str, object]]:
    try:
        watchlist.remove(symbol)
        return watchlist.list_items()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
