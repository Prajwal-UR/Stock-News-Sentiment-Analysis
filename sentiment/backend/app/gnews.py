from __future__ import annotations

import asyncio
import hashlib
import math
import threading
import time
from datetime import date, datetime, time as datetime_time, timedelta, timezone

import httpx

from app.config import Settings
from app.news import (
    NewsArticle,
    NewsProviderError,
    _parse_article,
    deduplicate_and_filter,
)
from app.schemas import StockItem

GNEWS_SEARCH_URL = "https://gnews.io/api/v4/search"
GNEWS_ARCHIVE_START = date(2020, 1, 1)
GNEWS_RESULT_LIMIT = 1000


def _search_query(stock: StockItem) -> str:
    terms: list[str] = []
    for alias in stock.aliases:
        candidate = f'"{alias}"'
        if candidate not in terms and len(" OR ".join((*terms, candidate))) <= 200:
            terms.append(candidate)
    if not terms:
        raise NewsProviderError("No searchable company aliases are configured.", 422)
    return " OR ".join(terms)


def _iso_utc(value: date, end_of_day: bool = False) -> str:
    boundary = datetime_time.max if end_of_day else datetime_time.min
    return datetime.combine(value, boundary, tzinfo=timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def _parse_gnews_article(article: dict, query: str) -> NewsArticle | None:
    normalized = dict(article)
    source = article.get("source")
    if isinstance(source, dict):
        normalized["source"] = {"name": source.get("name")}
    return _parse_article(normalized, "GNews", query)


class GNewsProvider:
    name = "GNews"

    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self._client = client
        self._cache: dict[str, tuple[float, list[NewsArticle], datetime, int]] = {}
        self._cache_lock = threading.Lock()
        self._request_lock = asyncio.Lock()
        self._last_request_at: float | None = None

    async def search(
        self, stock: StockItem, start_date: date, end_date: date, limit: int
    ) -> tuple[list[NewsArticle], str, datetime, int]:
        if self.settings.news_provider.casefold() != "gnews":
            raise NewsProviderError("Unsupported news provider. Configure NEWS_PROVIDER=gnews.", 503)
        if not self.settings.gnews_api_key.strip():
            raise NewsProviderError(
                "GNEWS_API_KEY is not configured. Add it to sentiment/backend/.env to use GNews.",
                503,
            )
        if limit < 1:
            raise NewsProviderError("At least one article must be requested.", 422)
        if start_date > end_date:
            raise NewsProviderError("Start date must be on or before end date.", 422)
        if self.settings.gnews_max_age_days:
            earliest = date.today() - timedelta(days=self.settings.gnews_max_age_days - 1)
            if start_date < earliest:
                raise NewsProviderError(
                    f"This GNews configuration supports only the most recent "
                    f"{self.settings.gnews_max_age_days} days. Configure "
                    "GNEWS_MAX_AGE_DAYS according to your verified subscription archive.",
                    422,
                )
        elif start_date < GNEWS_ARCHIVE_START:
            raise NewsProviderError(
                "GNews historical search is supported from 2020-01-01 onward. "
                "Choose a date in that archive or verify your plan's coverage.",
                422,
            )

        query = _search_query(stock)
        cache_key = hashlib.sha256(
            f"{stock.symbol}|{start_date}|{end_date}|{limit}".encode()
        ).hexdigest()
        ttl = self.settings.news_cache_ttl_seconds
        now = time.monotonic()
        if ttl > 0:
            with self._cache_lock:
                cached = self._cache.get(cache_key)
            if cached and now - cached[0] < ttl:
                return cached[1][:limit], "hit", cached[2], cached[3]

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.settings.request_timeout_seconds)
        request_limit = min(limit, GNEWS_RESULT_LIMIT)
        page_size = min(request_limit, self.settings.gnews_page_size)
        max_pages = math.ceil(request_limit / page_size)
        retrieved_count = 0
        total_articles = request_limit
        parsed_articles: list[NewsArticle] = []
        filtered: list[NewsArticle] = []
        try:
            for page in range(1, max_pages + 1):
                page_limit = min(page_size, request_limit - retrieved_count)
                async with self._request_lock:
                    if self._last_request_at is not None:
                        delay = self.settings.gnews_request_interval_seconds - (
                            time.monotonic() - self._last_request_at
                        )
                        if delay > 0:
                            await asyncio.sleep(delay)
                    response = await client.get(
                        GNEWS_SEARCH_URL,
                        params={
                            "q": query,
                            "from": _iso_utc(start_date),
                            "to": _iso_utc(end_date, end_of_day=True),
                            "lang": "en",
                            "sortby": "publishedAt",
                            "max": page_limit,
                            "page": page,
                        },
                        headers={"X-Api-Key": self.settings.gnews_api_key},
                    )
                    self._last_request_at = time.monotonic()
                if response.status_code in (401, 403):
                    raise NewsProviderError("GNews authentication failed. Check GNEWS_API_KEY and plan access.", 502)
                if response.status_code == 429:
                    raise NewsProviderError("GNews rate limit reached. Wait before trying again.", 429)
                if response.status_code != 200:
                    raise NewsProviderError(f"GNews returned HTTP {response.status_code}.", 502)
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise NewsProviderError("GNews returned an invalid response.", 502) from exc
                if not isinstance(payload, dict):
                    raise NewsProviderError("GNews returned an invalid response.", 502)
                provider_articles = payload.get("articles")
                if not isinstance(provider_articles, list):
                    raise NewsProviderError("GNews returned an invalid article list.", 502)
                total = payload.get("totalArticles")
                if isinstance(total, int) and total >= 0:
                    total_articles = min(total, GNEWS_RESULT_LIMIT)
                retrieved_count += len(provider_articles)
                parsed_articles.extend(
                    parsed
                    for item in provider_articles
                    if isinstance(item, dict)
                    if (parsed := _parse_gnews_article(item, query)) is not None
                )
                filtered = deduplicate_and_filter(parsed_articles, stock, limit)
                if (
                    len(filtered) >= limit
                    or not provider_articles
                    or len(provider_articles) < page_limit
                    or retrieved_count >= total_articles
                    or retrieved_count >= request_limit
                ):
                    break
        except httpx.TimeoutException as exc:
            raise NewsProviderError("GNews request timed out. Try again later.", 504) from exc
        except httpx.RequestError as exc:
            raise NewsProviderError("Could not connect to GNews.", 502) from exc
        finally:
            if owns_client:
                await client.aclose()

        retrieved_at = datetime.now(timezone.utc)
        if ttl > 0:
            with self._cache_lock:
                self._cache[cache_key] = (time.monotonic(), filtered, retrieved_at, retrieved_count)
        return filtered, "miss" if ttl else "disabled", retrieved_at, retrieved_count
