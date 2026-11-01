from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FundamentalMetric:
    label: str
    value: float | int | None
    source: str
    currency: str | None
    reporting_period: str | None


_FIELDS = (
    ("Market capitalization", "marketCap"),
    ("P/E ratio", "trailingPE"),
    ("P/B ratio", "priceToBook"),
    ("Earnings per share", "trailingEps"),
    ("Revenue growth", "revenueGrowth"),
    ("Earnings growth", "earningsGrowth"),
    ("Return on equity", "returnOnEquity"),
    ("Debt-to-equity", "debtToEquity"),
    ("Dividend yield", "dividendYield"),
    ("Free cash flow", "freeCashflow"),
)


def _format_period(value: object) -> str | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(value, timezone.utc).date().isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    return str(value) if value else None


def extract_fundamentals(info: dict[str, Any]) -> list[FundamentalMetric]:
    currency = info.get("financialCurrency") or info.get("currency")
    period = info.get("mostRecentQuarter") or info.get("lastFiscalYearEnd")
    result = []
    for label, key in _FIELDS:
        value = info.get(key)
        if not isinstance(value, (float, int)) or isinstance(value, bool):
            value = None
        elif key == "dividendYield" and value > 0.1:
            value /= 100
        result.append(
            FundamentalMetric(
                label=label,
                value=value,
                source="Yahoo Finance (unofficial, via yfinance)",
                currency=currency if label in {
                    "Market capitalization", "Earnings per share", "Free cash flow"
                } else None,
                reporting_period=_format_period(period),
            )
        )
    return result
