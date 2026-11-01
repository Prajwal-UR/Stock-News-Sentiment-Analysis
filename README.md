# StockQ — Equity Research Website

StockQ is a standalone responsive website for Indian equity-market research. A FastAPI service exposes provider-sourced OHLCV and fundamentals alongside reproducible technical indicators, an evaluated forecasting example, historical risk measures, a rule-based research summary, stock comparison, and a local watchlist.

> This is not investment advice. Prices and company information come from Yahoo Finance through `yfinance`, an unofficial data-access option. Coverage, timing, accuracy, and availability are not guaranteed; the dashboard never describes its data as exchange-grade or guaranteed live. Forecasts are estimates, not guaranteed outcomes.

## Run locally

Requires Python 3.10 or later (Python 3.14 is suitable if all dependencies resolve).

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn server:app --reload
```

Open `http://127.0.0.1:8000` in a browser. The JSON API and interactive API documentation are available at `/api` and `/docs` respectively (`/api/health` is the health check). The `.env.example` file documents optional environment settings. Set those variables in the shell or your deployment's environment configuration; the service does not load `.env` files. No API key is required for Yahoo Finance access. A network connection is required for market data.

## Financial news sentiment module

The independently deployable React/FastAPI sentiment module is in [sentiment/](sentiment/README.md). It is separate from the main price-analysis dashboard and has its own setup instructions, news provider configuration, and tests.

## Configuration and behavior

| Variable | Default | Description |
| --- | --- | --- |
| `STOCKQ_CACHE_TTL_SECONDS` | `300` | In-memory market response cache duration. Cache status is displayed. |
| `STOCKQ_REQUEST_TIMEOUT_SECONDS` | `15` | Provider download timeout in seconds. |
| `STOCKQ_WATCHLIST_PATH` | `.stockq/watchlist.json` | Local watchlist file path. |

The stock selector includes the NIFTY 50, NIFTY Next 50, and NIFTY Midcap 150 constituents from the [official Nifty Indices constituent files](https://www.niftyindices.com/IndexConstituent/), stored in `data/nifty_index_constituents.json` (snapshot dated 2026-10-27). Refresh this snapshot from the official files when index membership changes. Ticker resolution is implemented in `stockq/config.py`; other provider-compatible tickers may also be entered directly. Yahoo Finance symbols commonly use `.NS` for NSE and `.BO` for BSE. The application does not silently replace missing or failed data with sample prices. The watchlist stores symbols and selected period/horizon locally; do not place sensitive information in it.

## Features and limits

- **Market overview and charts:** adjusted daily OHLCV, period high/low, daily change, volume, line or candlestick view, chart overlays, and 52-week range when observations span at least 364 calendar days.
- **Fundamentals:** best-effort provider-reported metrics. Missing values display as unavailable; reporting metadata may be incomplete and is shown when returned.
- **Forecast:** Random Forest compared with persistence and five-session moving-average baselines; chronological splits, held-out test metrics, MAE, RMSE, and directional accuracy. Forecast target dates use business days and do not model Indian market holidays. This is not a backtest or profitability claim.
- **Research:** transparent rule-based interpretation; no LLM is called and no API credential is required. Statements derive from displayed price history.
- **Comparison:** normalizes adjusted-price series to 100 at the first common trading session, with matched-date metrics and available fundamental fields.
- **Persistence:** JSON watchlist is intentionally replaceable and local to this standalone module.
- **Website:** responsive browser UI with keyboard-accessible controls, interactive chart tooltips and overlays, theme toggle, and API-backed analysis; the frontend is served by FastAPI without Streamlit or external chart dependencies.

Yahoo Finance can be rate-limited, delayed, missing fundamentals, or unavailable. Provider failures appear as errors. The cache is in-memory for the running process and is not a stale-data fallback.

## Tests

```powershell
python -m unittest discover -s tests -v
```

Tests use small generated price series only as isolated test fixtures; generated values are never exposed by the application as market data.

## Formula and methodology reference

See [docs/FORMULAS.md](docs/FORMULAS.md) for indicator definitions, risk thresholds, and forecast split methodology.

## Integrating with the main StockQ project

See [docs/INTEGRATION.md](docs/INTEGRATION.md) for module interfaces and replacement points for provider and persistence.
