# Integrating the sentiment module with StockQ

The sentiment feature is an independent FastAPI service and React frontend. Existing StockQ routes, authentication, market-analysis modules, and persistence are not modified by this module. For independent deployment run the backend and frontend separately as described in [`README.md`](README.md).

## Call the versioned API

The main frontend sends a same-origin request through its backend proxy, or calls the separately deployed sentiment API origin:

```http
POST /api/v1/sentiment/analyze
Content-Type: application/json
```

```json
{
  "symbol": "RELIANCE.NS",
  "exchange": "NSE",
  "start_date": "2026-10-20",
  "end_date": "2026-10-26",
  "max_articles": 30,
  "demo_mode": false
}
```

For live analysis `demo_mode` is `false`; synthetic fixtures are accepted only if the backend operator explicitly sets `ENABLE_DEMO_MODE=true` for development/testing. The JSON response contains:

- `stock`, `period`, and `source` metadata (provider, mode, provider retrieval timestamp, analysis timestamp, provider/inference cache state, retrieved/eligible counts, model identifier).
- `sentiment.overall_label`, `net_score`, `mean_probabilities`, and class counts/percentages.
- `trend`, grouped by dates that actually contain eligible articles.
- `articles`, with original `url`, publisher, provider timestamp, headline, optional description, class probabilities, label, score, model identifier, and analysis timestamp.
- `summary`, with evidence items linked to their actual article URLs and explicit limitations.
- `warnings`, including insufficient evidence, empty results, or demo status.

Related endpoints: `GET /api/v1/health`, `GET /api/v1/stocks`, `GET /api/v1/sentiment/sources`. `/docs` publishes the interactive OpenAPI schema.

The main application should treat `net_score: null` and `overall_label: "No eligible news"` as no result, not as a neutral observation. Display provider/cache freshness and demo-mode warnings alongside model output. Do not present model probabilities as future-return probabilities. Demo mode is disabled by default, and if enabled must remain an explicit user choice.

## CORS and deployment

Prefer a same-origin reverse proxy for the main application. If the main frontend calls the sentiment service directly, set the backend's `FRONTEND_ORIGINS` to an exact comma-separated list, such as:

```env
APP_ENV=production
FRONTEND_ORIGINS=https://stockq.example.edu
```

Production CORS has no wildcard/default frontend origin. Keep `NEWS_API_KEY` on the backend only. Deploy the FastAPI service and built Vite frontend independently; browser builds use `VITE_API_BASE_URL` only for the public API base URL, never provider/model secrets. Confirm NewsAPI plan limits and permitted caching/content use before deployment.

## Replaceable interfaces

- Implement `NewsProvider.search(stock, start_date, end_date, limit)` to replace NewsAPI.
- Implement `SentimentClassifier.classify(texts)` to replace/extend the FinBERT classifier.
- Replace `TTLCache` with a licensed, shared cache without changing the aggregation contract.
- Keep `aggregate_sentiment` and `build_evidence_summary` independent of the UI and provider.

The host project can consume the JSON API or import those backend services. This module deliberately has no dependency on host authentication, database schemas, routing, or portfolio logic.
