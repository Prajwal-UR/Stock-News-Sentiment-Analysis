# Integration guide

This module has no mandatory authentication or main-application database dependency. Core analysis functions accept pandas series/data frames and can be imported independently of the web UI.

## Module boundaries

- `stockq.market_data.MarketDataProvider`: replace Yahoo Finance with an exchange-authorized or otherwise approved provider. A provider returns `MarketData` containing a validated OHLCV frame, optional provider fundamentals, fetch timestamp, and cache status.
- `stockq.indicators.calculate_indicators`, `stockq.risk.assess_risk`, and `stockq.research.build_research_summary`: deterministic analytics with no UI dependency.
- `stockq.forecasting.forecast_close`: independently testable forecasting/evaluation interface.
- `stockq.persistence.JsonWatchlistStore`: small persistence adapter; replace with the host application's repository or database adapter.
- `server.py`: FastAPI route layer; it calls the module services and does not own calculation formulas.
- `web/`: standalone responsive browser UI using the JSON API; chart rendering uses the browser canvas.

The JSON API provides `/api/analysis`, `/api/compare`, `/api/stocks`, and `/api/watchlist`. Interactive API documentation is served at `/docs`. The frontend and API are same-origin when run with the documented Uvicorn command.

Start the web app with `python -m uvicorn server:app --reload`, then open `http://127.0.0.1:8000`.

## Reuse from another Python application

Install the dependencies from `requirements.txt`, then import the analysis functions. The main application can expose these calls through its own service/API layer and render the results in its existing frontend. Keep credentials in the host application's secret manager and inject provider configuration rather than committing secrets. Keep provider timestamps and freshness metadata with returned data.

```python
from stockq.indicators import calculate_indicators
from stockq.risk import assess_risk
from stockq.forecasting import forecast_close

indicators = calculate_indicators(validated_ohlcv)
risk = assess_risk(validated_ohlcv, indicators)
forecast = forecast_close(validated_ohlcv["Close"], horizon=5)
```

For production or academic evaluation, validate the chosen provider's licensing, exchange coverage, corporate-action handling, rate limits, and timestamps. Revisit forecast split design and thresholds for the intended use case; neither the current model nor the risk categories establish investment performance.
