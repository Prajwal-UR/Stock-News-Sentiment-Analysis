from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Stock:
    symbol: str
    name: str
    exchange: str
    currency: str = "INR"


_EXAMPLE_STOCKS = (
    Stock("RELIANCE.NS", "Reliance Industries", "NSE"),
    Stock("TCS.NS", "Tata Consultancy Services", "NSE"),
    Stock("HDFCBANK.NS", "HDFC Bank", "NSE"),
    Stock("INFY.NS", "Infosys", "NSE"),
    Stock("ICICIBANK.NS", "ICICI Bank", "NSE"),
    Stock("500325.BO", "Reliance Industries", "BSE"),
    Stock("532540.BO", "Tata Consultancy Services", "BSE"),
)

_CONSTITUENTS_FILE = Path(__file__).resolve().parents[1] / "data" / "nifty_index_constituents.json"
with _CONSTITUENTS_FILE.open(encoding="utf-8") as constituents_file:
    _CONSTITUENT_DATA = json.load(constituents_file)

_INDEX_STOCKS = tuple(
    Stock(f"{item['symbol']}.NS", item["company_name"], "NSE")
    for item in _CONSTITUENT_DATA["constituents"]
)
EXAMPLE_STOCKS = tuple({
    stock.symbol: stock for stock in (*_INDEX_STOCKS, *_EXAMPLE_STOCKS)
}.values())

PERIODS = {
    "1 month": "1mo",
    "3 months": "3mo",
    "6 months": "6mo",
    "1 year": "1y",
    "5 years": "5y",
    "Maximum": "max",
}

_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9.&_-]{0,24}(?:\.(?:NS|BO))?$")


def resolve_symbol(query: str, exchange: str = "NSE") -> Stock:
    if exchange not in {"NSE", "BSE"}:
        raise ValueError("Exchange must be NSE or BSE.")
    cleaned = query.strip()
    if not cleaned:
        raise ValueError("Enter a company name or ticker symbol.")

    matches = [stock for stock in EXAMPLE_STOCKS if stock.name.casefold() == cleaned.casefold()]
    if matches:
        return next((stock for stock in matches if stock.exchange == exchange), matches[0])

    normalized = cleaned.upper()
    if not _SYMBOL_PATTERN.fullmatch(normalized):
        raise ValueError("Invalid symbol. Use a ticker such as RELIANCE or RELIANCE.NS.")
    if normalized.endswith((".NS", ".BO")):
        suffix_exchange = "NSE" if normalized.endswith(".NS") else "BSE"
        return Stock(normalized, normalized.rsplit(".", 1)[0], suffix_exchange)

    suffix = ".NS" if exchange == "NSE" else ".BO"
    known = next((stock for stock in EXAMPLE_STOCKS if stock.symbol == normalized + suffix), None)
    if known:
        return known
    return Stock(normalized + suffix, normalized, exchange)


def cache_ttl_seconds() -> int:
    return max(0, int(os.getenv("STOCKQ_CACHE_TTL_SECONDS", "300")))


def request_timeout_seconds() -> int:
    return max(1, int(os.getenv("STOCKQ_REQUEST_TIMEOUT_SECONDS", "15")))
