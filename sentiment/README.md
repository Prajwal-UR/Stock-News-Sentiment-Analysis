# StockQ Financial News Sentiment

An independently deployable financial-news sentiment module for Indian equities. The React/TypeScript/Vite dashboard calls a versioned FastAPI API; the backend retrieves provider-attributed news, filters/deduplicates it, classifies article text with lazy-loaded ProsusAI/finbert, and calculates explainable aggregates. It is separate from the root StockQ market-analysis website and does not add forecasts, technical indicators, or trading recommendations.

## Start locally

Requires Python 3.10+ and Node.js 20+.

### Backend

```powershell
cd sentiment\backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Set NEWS_API_KEY in .env before requesting real news.
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

Get a NewsAPI key at [newsapi.org/register](https://newsapi.org/register), put it only in `sentiment\backend\.env` as `NEWS_API_KEY=...`, and restart the backend. The API key is not included in frontend requests. The application allows date searches within the latest 30 days by default; NewsAPI remains authoritative and may reject dates unavailable to the configured account.

The backend uses the NewsAPI Everything endpoint, searches company aliases in headlines, filters language/relevance, deduplicates results, and paginates up to five provider pages to fill the eligible article limit. The frontend shows provider-retrieved and eligible counts separately. Provider access and historical coverage depend on your account, and provider caching/content terms must be checked before deployment.

The company selector includes the NIFTY 50, NIFTY Next 50, and NIFTY Midcap 150 constituents from the [official Nifty Indices constituent files](https://www.niftyindices.com/IndexConstituent/), with a local snapshot dated 2026-10-27 in `data/nifty_index_constituents.json`. Refresh the shared snapshot from the official files when membership changes; symbols are sent to Yahoo Finance and name/ticker aliases are used for news search and relevance filtering.

ProsusAI/finbert is loaded once on the first eligible real-news analysis and reused. Initial model download requires network access and sufficient disk, memory, and compute. If loading or inference fails, the API returns a model-specific error and never switches to heuristic output. The [model card](https://huggingface.co/ProsusAI/finbert) currently lists model weights under **CC BY-NC-SA 4.0**, which restricts commercial use and requires share-alike terms for adaptations; confirm the terms and whether your project use qualifies before deployment.

Synthetic fixtures are disabled by default. To expose the explicitly labeled development-only demo control, set `ENABLE_DEMO_MODE=true` in the backend `.env`; demo responses use only synthetic fixtures and the demo heuristic, and are never mixed with provider articles. Leave it `false` for real-data demonstrations.

### Frontend

In a second terminal:

```powershell
cd sentiment\frontend
npm ci
npm run dev
```

Open the Vite URL shown in the terminal (normally `http://localhost:5173`). The dev server proxies `/api` requests to `http://127.0.0.1:8001`. For a deployed backend on another origin, set `VITE_API_BASE_URL` in the frontend environment and add that exact frontend origin to backend `FRONTEND_ORIGINS`.

The stock selector and analysis header load company logos by ticker from Logo.dev when `VITE_LOGO_DEV_PUBLISHABLE_KEY` is set in `sentiment/frontend/.env.local`; the browser-visible key is a publishable key, not a secret. Logo lookup uses the existing ticker (for example, `RELIANCE.NS`) and falls back to a locally rendered ticker monogram if the key is not configured or Logo.dev cannot provide the image. Logo availability for each NSE symbol depends on Logo.dev's coverage and account. Review Logo.dev's current pricing and attribution terms before commercial use.

## News provider

NewsAPI remains the default provider and uses its documented `/v2/everything` endpoint. To opt in to GNews, set `NEWS_PROVIDER=gnews` and `GNEWS_API_KEY` in `sentiment/backend/.env`; provider keys stay on the backend and must never be placed in a `VITE_*` variable or committed. The sentiment pipeline and API request/response contract are the same for both providers.

NewsAPI access is plan-dependent. Historical coverage, daily request quotas, permitted use, and caching/content terms depend on the account and may change. The UI defaults to the last 30 days, offers a 7-day preset, and allows a custom date range within the latest 30 days. The backend enforces the same maximum date window. This module does not depend on a 2020-onward archive.

GNews search supports date filters and paging, but a search is limited to 1,000 results and a plan-specific maximum per page. `GNEWS_PAGE_SIZE` defaults to 10 (the Free plan's documented maximum); set it to the maximum allowed by your active plan to use larger pages. Each analysis requests no more than its specified article limit and paginates only as needed; it does not download a multi-year archive. `GNEWS_REQUEST_INTERVAL_SECONDS` defaults to one request per second (the documented Free-plan rate); set it to the rate permitted by your plan. `GNEWS_MAX_AGE_DAYS` defaults to 30 as a safe Free-plan cap. Set it to 0 only after verifying that your account has paid-plan historical access; in that configuration the local validation allows dates from 2020-01-01, which is the earliest archive date GNews advertises for paid plans. GNews may return an empty result for dates outside a plan's archive, so this local setting must accurately reflect the subscription. An empty provider response is never replaced with synthetic data.

GNews's published pricing lists Free (€0, non-commercial, 100 requests/day, 10 articles/request), Essential (€49.99/month, 1,000/day, 25/request), Business (€99.99/month, 5,000/day, 50/request), and Enterprise (€249.99/month, 25,000/day, 100/request); its plans page advertises a 10-day trial. Pricing and availability can change. Its terms restrict free use to non-commercial purposes and require an active paid subscription for commercial API use. The terms also permit reasonable performance caching but prohibit systematic downloads to build a competing database or avoid quotas. A GNews subscription does not grant rights to third-party publisher content. Verify current pricing, plan archive access, and rights for displaying or retaining article content before production use.

The GNews docs advertise paid archives since 2020 and provide India as a source-country filter; this does not establish that articles exist for every Indian company/date, and source country does not mean the story is about an Indian company. No live GNews account/key is configured here, so company-specific historical result availability has not been tested. Check current provider limits and terms before deployment.

Only titles, provider descriptions, publisher, provider timestamp, and canonical source URLs returned by the provider are processed. Full article content is not fetched. Results are temporarily cached in process memory according to `NEWS_CACHE_TTL_SECONDS`; each cache hit returns its original retrieval timestamp. Do not enable caching beyond provider licensing terms.

## Backend API

Open `http://127.0.0.1:8001/docs` for OpenAPI documentation.

- `GET /api/v1/health`: provider configuration status and model identifier (never secrets).
- `GET /api/v1/stocks`: configured companies, exchange, symbol, search aliases.
- `GET /api/v1/sentiment/sources`: configured source/model status.
- `POST /api/v1/sentiment/analyze`: body fields `symbol`, `exchange`, `start_date`, `end_date`, `max_articles`, and `demo_mode` (false for real analysis).

Example request:

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

The response includes the selected stock and requested dates; actual provider retrieval time and analysis timestamp; provider-retrieved and eligible article counts; provider and inference cache state; model identity; overall score/label; counts, percentages, probability means; observed-day trend; individual article source links, timestamps, labels, probabilities, and scores; an evidence-linked deterministic summary; and warnings. Empty results have a `No eligible news` label and null score/percentages, not an invented neutral score. Invalid requests return 422, provider errors use appropriate 429/502/503/504 statuses, and model errors are returned separately as 503. Messages do not expose API keys or tracebacks.

## Methodology and safeguards

For each real article, ProsusAI/finbert tokenizes the retrieved headline and available provider description and computes the positive, negative, and neutral class probabilities. `article_score = positive_probability - negative_probability`, range −1 to +1. The overall score is the equal-weight arithmetic mean. It is labelled Positive only when greater than +0.10, Negative only when below −0.10, and Neutral or mixed inside the inclusive interval. Fewer than three eligible articles is marked insufficient evidence; this minimum and the thresholds are project heuristics, not validated investment thresholds. With zero articles, no aggregate score is reported.

Article labels use the highest FinBERT class probability (Positive/Negative/Neutral); class probabilities are validated to be in [0,1] and sum approximately to 1. They are model confidence values, not calibrated share-price probabilities. Headlines and available descriptions are combined, length-limited, and batched. Missing descriptions are flagged as headline-only. FinBERT is not claimed to be trained specifically on Indian market news.

Configured full company names and aliases are used for provider search and a second relevance check. Stories are deduplicated by canonical URL and normalized headline, so syndicated duplicates are less likely to count as independent evidence. Daily trends group by publication timestamp/date and include only dates with eligible articles; the frontend leaves gaps visible rather than fabricating zero-article observations. The deterministic evidence summary links representative actual article headlines; it does not infer causes or future returns.

## Configuration

See [`backend/.env.example`](backend/.env.example). Important settings:

| Variable | Default | Meaning |
| --- | --- | --- |
| `NEWS_PROVIDER` | `newsapi` | Provider adapter selection. |
| `NEWS_API_KEY` | empty | Secret for server-side NewsAPI requests. |
| `NEWS_MAX_AGE_DAYS` | `30` | Maximum age allowed by the application for NewsAPI searches; actual provider plan limits may be narrower. |
| `GNEWS_API_KEY` | empty | Secret for server-side GNews requests. |
| `GNEWS_MAX_AGE_DAYS` | `30` | Local GNews age cap; use 0 only for a verified paid archive (since 2020). |
| `GNEWS_PAGE_SIZE` | `10` | Per-request GNews page size; do not exceed the maximum for your subscription tier. |
| `GNEWS_REQUEST_INTERVAL_SECONDS` | `1.0` | Minimum time between GNews requests; adjust only to the rate allowed by your plan. |
| `FINBERT_MODEL` | `ProsusAI/finbert` | Hugging Face model identifier. |
| `ENABLE_DEMO_MODE` | `false` | Exposes synthetic fixtures only when `APP_ENV` is `development` or `test`. |
| `FRONTEND_ORIGINS` | development localhost origins | Comma-separated exact CORS origins. Production defaults to no allowed origins unless explicitly configured. |
| `NEWS_CACHE_TTL_SECONDS` | `300` | In-process article and inference-result cache TTL; set 0 to disable. |
| `REQUEST_TIMEOUT_SECONDS` | `12` | HTTP provider timeout. |
| `MIN_ARTICLES_FOR_CONCLUSION` | `3` | Below this count, overall status is insufficient evidence. |
| `MAX_ARTICLES_PER_REQUEST` | `100` | API article bound. |

## Tests and build

```powershell
cd sentiment\backend
python -m pip install -r requirements.txt
python -m pytest
```

Backend unit/API tests mock external NewsAPI and the model; test runs do not need a paid API key or model download.

```powershell
cd sentiment\frontend
npm ci
npm test
npm run build
```

## Main StockQ integration

See [`INTEGRATION.md`](INTEGRATION.md) for API request/response integration, deployment, CORS, and replacement interfaces.
