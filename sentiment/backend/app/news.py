from __future__ import annotations
import hashlib
import re
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from app.config import Settings
from app.schemas import StockItem
from app.stocks import matches_company

NEWS_API_URL = "https://newsapi.org/v2/everything"


class NewsProviderError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class NewsArticle:
    headline: str
    description: str | None
    publisher: str
    published_at: datetime
    url: str
    source_provider: str
    search_query: str = ""


class NewsProvider(Protocol):
    name: str

    async def search(
        self, stock: StockItem, start_date: date, end_date: date, limit: int
    ) -> tuple[list[NewsArticle], str, datetime, int]: ...


def canonical_url(url: str) -> str | None:
    try:
        parts = urlsplit(url.strip())
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            return None
        hostname = parts.hostname.casefold()
        if hostname.startswith("www."):
            hostname = hostname[4:]
        path = parts.path.rstrip("/") or "/"
        query = urlencode(sorted(
            (key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key.casefold() not in {"fbclid", "gclid", "ref", "source"}
            and not key.casefold().startswith("utm_")
        ))
        return urlunsplit((parts.scheme.casefold(), hostname, path, query, ""))
    except ValueError:
        return None


def normalized_headline(value: str) -> str:
    return re.sub(r"\W+", " ", value.casefold(), flags=re.UNICODE).strip()


def _is_historical_coverage_error(message: str) -> bool:
    lowered = message.casefold()
    return any(term in lowered for term in (
        "historical",
        "in the past",
        "date range",
        "past data",
        "month old",
        "older than",
        "not allowed to search",
        "historical coverage",
    ))


def deduplicate_and_filter(
    articles: list[NewsArticle], stock: StockItem, limit: int
) -> list[NewsArticle]:
    seen_urls: set[str] = set()
    seen_headlines: set[str] = set()
    result = []
    for article in articles:
        if not article.headline.strip() or not article.publisher.strip():
            continue
        combined = " ".join(filter(None, (article.headline, article.description)))
        if not matches_company(combined, stock):
            continue
        canonical = canonical_url(article.url)
        headline = normalized_headline(article.headline)
        if not canonical or not headline or canonical in seen_urls or headline in seen_headlines:
            continue
        seen_urls.add(canonical)
        seen_headlines.add(headline)
        result.append(
            NewsArticle(
                headline=article.headline.strip(),
                description=article.description.strip()[:1200] if article.description else None,
                publisher=article.publisher.strip(),
                published_at=article.published_at,
                url=canonical,
                source_provider=article.source_provider,
                search_query=article.search_query,
            )
        )
        if len(result) >= limit:
            break
    return result


def _parse_article(article: dict, provider_name: str, search_query: str) -> NewsArticle | None:
    title = article.get("title")
    published = article.get("publishedAt")
    source = article.get("source") or {}
    publisher = source.get("name") if isinstance(source, dict) else None
    url = article.get("url")
    if not all(isinstance(value, str) and value.strip() for value in (title, published, publisher, url)):
        return None
    try:
        published_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
    except ValueError:
        return None
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    description = article.get("description")
    return NewsArticle(
        headline=title.strip(),
        description=description.strip() if isinstance(description, str) and description.strip() else None,
        publisher=publisher.strip(),
        published_at=published_at.astimezone(timezone.utc),
        url=url,
        source_provider=provider_name,
        search_query=search_query,
    )


class NewsApiProvider:
    name = "NewsAPI"

    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self._client = client
        self._cache: dict[str, tuple[float, list[NewsArticle], datetime, int]] = {}
        self._cache_lock = threading.Lock()

    async def search(
        self, stock: StockItem, start_date: date, end_date: date, limit: int
    ) -> tuple[list[NewsArticle], str, datetime, int]:
        if self.settings.news_provider.casefold() != "newsapi":
            raise NewsProviderError("Unsupported news provider. Configure NEWS_PROVIDER=newsapi.", 503)
        if not self.settings.news_api_key.strip():
            raise NewsProviderError(
                "NEWS_API_KEY is not configured. Obtain a key from https://newsapi.org/register and set it in sentiment/backend/.env.",
                503,
            )
        if (
            self.settings.news_max_age_days
            and start_date < date.today() - timedelta(days=self.settings.news_max_age_days - 1)
        ):
            raise NewsProviderError(
                f"This NewsAPI configuration supports only the most recent {self.settings.news_max_age_days} days. "
                "Choose a newer start date or configure the historical coverage available on your NewsAPI plan.",
                422,
            )
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
        query = " OR ".join(f'"{term}"' for term in stock.aliases)
        page_size = min(limit, 100)
        page = 1
        total_results = 0
        retrieved_count = 0
        parsed_articles: list[NewsArticle] = []
        try:
            while page <= 5:
                response = await client.get(
                    NEWS_API_URL,
                    params={
                        "qInTitle": query,
                        "from": start_date.isoformat(),
                        "to": end_date.isoformat(),
                        "language": "en",
                        "sortBy": "publishedAt",
                        "pageSize": page_size,
                        "page": page,
                    },
                    headers={"X-Api-Key": self.settings.news_api_key},
                )
                if response.status_code in (401, 403):
                    raise NewsProviderError("News provider authentication failed. Check NEWS_API_KEY.", 502)
                if response.status_code == 429:
                    raise NewsProviderError("News provider rate limit reached. Wait before trying again.", 429)
                if response.status_code in (400, 426):
                    try:
                        error_payload = response.json()
                    except ValueError:
                        error_payload = {}
                    provider_message = (
                        str(error_payload.get("message", ""))
                        if isinstance(error_payload, dict)
                        else ""
                    )
                    if _is_historical_coverage_error(provider_message):
                        raise NewsProviderError(
                            "The requested dates are outside this NewsAPI plan's historical coverage. "
                            "Choose dates supported by your account or check its plan limits.",
                            422,
                        )
                if response.status_code != 200:
                    raise NewsProviderError(f"News provider returned HTTP {response.status_code}.", 502)
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise NewsProviderError("News provider returned an invalid response.", 502) from exc
                if not isinstance(payload, dict):
                    raise NewsProviderError("News provider returned an invalid response.", 502)
                if payload.get("status") == "error":
                    code = payload.get("code", "")
                    message = str(payload.get("message", "")).casefold()
                    if _is_historical_coverage_error(message):
                        raise NewsProviderError(
                            "The requested dates are outside this NewsAPI plan's historical coverage. "
                            "Choose dates supported by your account or check its plan limits.",
                            422,
                        )
                    status = 429 if code == "rateLimited" else 502
                    raise NewsProviderError("News provider could not complete the request.", status)
                if payload.get("status") != "ok":
                    raise NewsProviderError("News provider returned an invalid response status.", 502)
                provider_articles = payload.get("articles", [])
                if not isinstance(provider_articles, list):
                    raise NewsProviderError("News provider returned an invalid article list.", 502)
                total_results = payload.get("totalResults", 0)
                if not isinstance(total_results, int) or total_results < 0:
                    total_results = 0
                retrieved_count += len(provider_articles)
                parsed_articles.extend(
                    parsed for item in provider_articles if isinstance(item, dict)
                    if (parsed := _parse_article(item, self.name, query)) is not None
                )
                filtered = deduplicate_and_filter(parsed_articles, stock, limit)
                if len(filtered) >= limit or retrieved_count >= total_results or len(provider_articles) < page_size:
                    break
                page += 1
        except httpx.TimeoutException as exc:
            raise NewsProviderError("News provider request timed out. Try again later.", 504) from exc
        except httpx.RequestError as exc:
            raise NewsProviderError("Could not connect to the news provider.", 502) from exc
        finally:
            if owns_client:
                await client.aclose()

        retrieved_at = datetime.now(timezone.utc)
        if ttl > 0:
            with self._cache_lock:
                self._cache[cache_key] = (time.monotonic(), filtered, retrieved_at, retrieved_count)
        return filtered, "miss" if ttl else "disabled", retrieved_at, retrieved_count
