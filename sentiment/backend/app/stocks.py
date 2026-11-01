from __future__ import annotations

import json
import re
from pathlib import Path

from app.schemas import StockItem


_CURATED_STOCKS = (
    StockItem(
        symbol="RELIANCE.NS", exchange="NSE", company_name="Reliance Industries",
        aliases=["Reliance Industries", "Reliance Industries Limited", "RIL", "RELIANCE.NS"],
    ),
    StockItem(
        symbol="HDFCBANK.NS", exchange="NSE", company_name="HDFC Bank",
        aliases=["HDFC Bank", "HDFC Bank Limited", "HDFCBANK.NS"],
    ),
    StockItem(
        symbol="INFY.NS", exchange="NSE", company_name="Infosys",
        aliases=["Infosys", "Infosys Limited", "INFY.NS"],
    ),
    StockItem(
        symbol="TCS.NS", exchange="NSE", company_name="Tata Consultancy Services",
        aliases=["Tata Consultancy Services", "TCS.NS", "TCS"],
    ),
    StockItem(
        symbol="ICICIBANK.NS", exchange="NSE", company_name="ICICI Bank",
        aliases=["ICICI Bank", "ICICI Bank Limited", "ICICIBANK.NS"],
    ),
    StockItem(
        symbol="ADANIENT.NS", exchange="NSE", company_name="Adani Enterprises",
        aliases=["Adani Enterprises", "Adani Enterprises Limited", "ADANIENT.NS"],
    ),
    StockItem(
        symbol="ADANIPORTS.NS", exchange="NSE", company_name="Adani Ports and Special Economic Zone",
        aliases=["Adani Ports", "Adani Ports and Special Economic Zone", "ADANIPORTS.NS"],
    ),
    StockItem(
        symbol="APOLLOHOSP.NS", exchange="NSE", company_name="Apollo Hospitals Enterprise",
        aliases=["Apollo Hospitals", "Apollo Hospitals Enterprise", "APOLLOHOSP.NS"],
    ),
    StockItem(
        symbol="ASIANPAINT.NS", exchange="NSE", company_name="Asian Paints",
        aliases=["Asian Paints", "ASIANPAINT.NS"],
    ),
    StockItem(
        symbol="AXISBANK.NS", exchange="NSE", company_name="Axis Bank",
        aliases=["Axis Bank", "AXISBANK.NS"],
    ),
    StockItem(
        symbol="BAJAJ-AUTO.NS", exchange="NSE", company_name="Bajaj Auto",
        aliases=["Bajaj Auto", "Bajaj Auto Limited", "BAJAJ-AUTO.NS"],
    ),
    StockItem(
        symbol="BAJFINANCE.NS", exchange="NSE", company_name="Bajaj Finance",
        aliases=["Bajaj Finance", "Bajaj Finance Limited", "BAJFINANCE.NS"],
    ),
    StockItem(
        symbol="BAJAJFINSV.NS", exchange="NSE", company_name="Bajaj Finserv",
        aliases=["Bajaj Finserv", "Bajaj Finserv Limited", "BAJAJFINSV.NS"],
    ),
    StockItem(
        symbol="BEL.NS", exchange="NSE", company_name="Bharat Electronics",
        aliases=["Bharat Electronics", "Bharat Electronics Limited", "BEL.NS"],
    ),
    StockItem(
        symbol="BHARTIARTL.NS", exchange="NSE", company_name="Bharti Airtel",
        aliases=["Bharti Airtel", "Bharti Airtel Limited", "BHARTIARTL.NS"],
    ),
    StockItem(
        symbol="CIPLA.NS", exchange="NSE", company_name="Cipla",
        aliases=["Cipla", "Cipla Limited", "CIPLA.NS"],
    ),
    StockItem(
        symbol="COALINDIA.NS", exchange="NSE", company_name="Coal India",
        aliases=["Coal India", "Coal India Limited", "COALINDIA.NS"],
    ),
    StockItem(
        symbol="DRREDDY.NS", exchange="NSE", company_name="Dr. Reddy's Laboratories",
        aliases=["Dr. Reddy's Laboratories", "Dr Reddy's", "DRREDDY.NS"],
    ),
    StockItem(
        symbol="EICHERMOT.NS", exchange="NSE", company_name="Eicher Motors",
        aliases=["Eicher Motors", "Eicher Motors Limited", "EICHERMOT.NS"],
    ),
    StockItem(
        symbol="GRASIM.NS", exchange="NSE", company_name="Grasim Industries",
        aliases=["Grasim Industries", "Grasim Industries Limited", "GRASIM.NS"],
    ),
    StockItem(
        symbol="HCLTECH.NS", exchange="NSE", company_name="HCL Technologies",
        aliases=["HCL Technologies", "HCLTech", "HCLTECH.NS"],
    ),
    StockItem(
        symbol="HINDALCO.NS", exchange="NSE", company_name="Hindalco Industries",
        aliases=["Hindalco Industries", "Hindalco", "HINDALCO.NS"],
    ),
    StockItem(
        symbol="HINDUNILVR.NS", exchange="NSE", company_name="Hindustan Unilever",
        aliases=["Hindustan Unilever", "Hindustan Unilever Limited", "HINDUNILVR.NS"],
    ),
    StockItem(
        symbol="INDUSINDBK.NS", exchange="NSE", company_name="IndusInd Bank",
        aliases=["IndusInd Bank", "IndusInd Bank Limited", "INDUSINDBK.NS"],
    ),
    StockItem(
        symbol="ITC.NS", exchange="NSE", company_name="ITC",
        aliases=["ITC", "ITC Limited", "ITC.NS"],
    ),
    StockItem(
        symbol="JIOFIN.NS", exchange="NSE", company_name="Jio Financial Services",
        aliases=["Jio Financial Services", "Jio Financial", "JIOFIN.NS"],
    ),
    StockItem(
        symbol="JSWSTEEL.NS", exchange="NSE", company_name="JSW Steel",
        aliases=["JSW Steel", "JSW Steel Limited", "JSWSTEEL.NS"],
    ),
    StockItem(
        symbol="KOTAKBANK.NS", exchange="NSE", company_name="Kotak Mahindra Bank",
        aliases=["Kotak Mahindra Bank", "Kotak Bank", "KOTAKBANK.NS"],
    ),
    StockItem(
        symbol="LT.NS", exchange="NSE", company_name="Larsen and Toubro",
        aliases=["Larsen and Toubro", "Larsen & Toubro", "LT.NS"],
    ),
    StockItem(
        symbol="M&M.NS", exchange="NSE", company_name="Mahindra and Mahindra",
        aliases=["Mahindra and Mahindra", "Mahindra & Mahindra", "M&M.NS"],
    ),
    StockItem(
        symbol="MARUTI.NS", exchange="NSE", company_name="Maruti Suzuki India",
        aliases=["Maruti Suzuki", "Maruti Suzuki India", "MARUTI.NS"],
    ),
    StockItem(
        symbol="NESTLEIND.NS", exchange="NSE", company_name="Nestle India",
        aliases=["Nestle India", "Nestle India Limited", "NESTLEIND.NS"],
    ),
    StockItem(
        symbol="NTPC.NS", exchange="NSE", company_name="NTPC",
        aliases=["NTPC", "NTPC Limited", "NTPC.NS"],
    ),
    StockItem(
        symbol="ONGC.NS", exchange="NSE", company_name="Oil and Natural Gas Corporation",
        aliases=["Oil and Natural Gas Corporation", "ONGC", "ONGC.NS"],
    ),
    StockItem(
        symbol="POWERGRID.NS", exchange="NSE", company_name="Power Grid Corporation of India",
        aliases=["Power Grid Corporation", "Power Grid Corporation of India", "POWERGRID.NS"],
    ),
    StockItem(
        symbol="SBIN.NS", exchange="NSE", company_name="State Bank of India",
        aliases=["State Bank of India", "SBI", "SBIN.NS"],
    ),
    StockItem(
        symbol="SUNPHARMA.NS", exchange="NSE", company_name="Sun Pharmaceutical Industries",
        aliases=["Sun Pharmaceutical Industries", "Sun Pharma", "SUNPHARMA.NS"],
    ),
    StockItem(
        symbol="TATACONSUM.NS", exchange="NSE", company_name="Tata Consumer Products",
        aliases=["Tata Consumer Products", "Tata Consumer", "TATACONSUM.NS"],
    ),
    StockItem(
        symbol="TATASTEEL.NS", exchange="NSE", company_name="Tata Steel",
        aliases=["Tata Steel", "Tata Steel Limited", "TATASTEEL.NS"],
    ),
    StockItem(
        symbol="TITAN.NS", exchange="NSE", company_name="Titan Company",
        aliases=["Titan Company", "Titan Company Limited", "TITAN.NS"],
    ),
    StockItem(
        symbol="ULTRACEMCO.NS", exchange="NSE", company_name="UltraTech Cement",
        aliases=["UltraTech Cement", "UltraTech Cement Limited", "ULTRACEMCO.NS"],
    ),
    StockItem(
        symbol="WIPRO.NS", exchange="NSE", company_name="Wipro",
        aliases=["Wipro", "Wipro Limited", "WIPRO.NS"],
    ),
)

_CONSTITUENTS_FILE = Path(__file__).resolve().parents[3] / "data" / "nifty_index_constituents.json"
with _CONSTITUENTS_FILE.open(encoding="utf-8") as constituents_file:
    _CONSTITUENTS_DATA = json.load(constituents_file)

_INDEX_STOCKS = tuple(
    StockItem(
        symbol=f"{item['symbol']}.NS",
        exchange="NSE",
        company_name=item["company_name"],
        aliases=[
            item["company_name"],
            re.sub(r"\s+(?:Ltd\.?|Limited)$", "", item["company_name"], flags=re.IGNORECASE),
            item["symbol"],
            f"{item['symbol']}.NS",
        ],
    )
    for item in _CONSTITUENTS_DATA["constituents"]
)
_stocks_by_symbol = {stock.symbol: stock for stock in _INDEX_STOCKS}
for _stock in _CURATED_STOCKS:
    existing = _stocks_by_symbol.get(_stock.symbol)
    if existing:
        _stocks_by_symbol[_stock.symbol] = existing.model_copy(
            update={"aliases": list(dict.fromkeys([*existing.aliases, *(_stock.aliases or [])]))}
        )
    else:
        _stocks_by_symbol[_stock.symbol] = _stock
STOCKS = tuple(_stocks_by_symbol.values())


def list_stocks() -> list[StockItem]:
    return list(STOCKS)


def find_stock(symbol: str, exchange: str) -> StockItem:
    normalized = symbol.strip().casefold()
    for stock in STOCKS:
        if stock.exchange == exchange and (
            stock.symbol.casefold() == normalized
            or stock.symbol.removesuffix(".NS").removesuffix(".BO").casefold() == normalized
            or stock.company_name.casefold() == normalized
        ):
            return stock
    raise ValueError(f"Unsupported stock symbol for {exchange}. Choose a configured company.")


def matches_company(text: str, stock: StockItem) -> bool:
    folded = text.casefold()
    symbol_aliases = {
        stock.symbol.casefold(),
        stock.symbol.removesuffix(".NS").removesuffix(".BO").casefold(),
    }
    for alias in stock.aliases:
        alias_folded = alias.casefold()
        if alias_folded in symbol_aliases or alias_folded in {"tcs", "ril", "itc", "sbi", "ntpc"}:
            if re.search(rf"(?<![a-z0-9]){re.escape(alias_folded)}(?![a-z0-9])", folded):
                return True
        elif alias_folded and alias_folded in folded:
            return True
    return False
