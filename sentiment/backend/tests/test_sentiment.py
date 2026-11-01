from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import httpx
import pytest
import sys
import types
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.aggregation import aggregate_sentiment, build_evidence_summary
from app.classifier import Classification, DemoRuleClassifier, FinBertClassifier, ModelInferenceError, classify_articles
from app.config import Settings
from app.gnews import GNewsProvider
from app.main import app
from app.news import (
    NewsApiProvider,
    NewsArticle,
    NewsProviderError,
    deduplicate_and_filter,
)
from app.schemas import (
    AnalyzeRequest,
    ArticleResult,
    Probabilities,
    SentimentLabel,
)
from app.service import SentimentService
from app.stocks import find_stock, list_stocks, matches_company

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
STOCK = find_stock("RELIANCE.NS", "NSE")


def news_article(
    headline: str = "Reliance Industries reports growth",
    url: str = "https://news.example/story?id=1",
    description: str | None = "Reliance Industries reports quarterly growth.",
    published_at: datetime = NOW,
) -> NewsArticle:
    return NewsArticle(
        headline=headline,
        description=description,
        publisher="Example News",
        published_at=published_at,
        url=url,
        source_provider="NewsAPI",
        search_query='"Reliance Industries"',
    )


def article_result(
    positive: float,
    negative: float,
    neutral: float,
    headline: str = "Reliance Industries headline",
    published_at: datetime = NOW,
) -> ArticleResult:
    label = max(
        (("Positive", positive), ("Negative", negative), ("Neutral", neutral)),
        key=lambda item: item[1],
    )[0]
    return ArticleResult(
        headline=headline,
        description=None,
        publisher="Example News",
        published_at=published_at,
        url="https://news.example/story",
        sentiment=SentimentLabel(label),
        probabilities=Probabilities(positive=positive, negative=negative, neutral=neutral),
        article_score=positive - negative,
        source_provider="Example News",
        search_query='"Reliance Industries"',
        model_id="test model",
        analyzed_at=NOW,
        analyzed_headline_only=True,
    )


class FixedClassifier:
    model_id = "unit-test-classifier"

    def __init__(self, scores: list[tuple[float, float, float]]) -> None:
        self.scores = scores
        self.calls = 0

    def classify(self, texts: list[str]) -> list[Classification]:
        self.calls += 1
        return [
            Classification(
                label=SentimentLabel(max(
                    (("Positive", score[0]), ("Negative", score[1]), ("Neutral", score[2])),
                    key=lambda item: item[1],
                )[0]),
                probabilities=Probabilities(
                    positive=score[0], negative=score[1], neutral=score[2]
                ),
            )
            for score in self.scores
        ]


class FailedClassifier:
    model_id = "ProsusAI/finbert"

    def classify(self, _texts: list[str]) -> list[Classification]:
        raise ModelInferenceError("FinBERT inference failed for the test.")


class FixedProvider:
    name = "Test provider"

    def __init__(self, articles: list[NewsArticle]) -> None:
        self.articles = articles
        self.calls = 0

    async def search(self, stock, start_date, end_date, limit):
        self.calls += 1
        return self.articles[:limit], "miss", NOW, len(self.articles[:limit])


def analyze_request(**overrides) -> AnalyzeRequest:
    values = {
        "symbol": "RELIANCE.NS",
        "exchange": "NSE",
        "start_date": date(2026, 10, 15),
        "end_date": date(2026, 10, 20),
        "max_articles": 10,
        "demo_mode": False,
    }
    values.update(overrides)
    return AnalyzeRequest(**values)


def test_aggregate_positive_negative_neutral_and_mean_probabilities():
    articles = [
        article_result(0.8, 0.1, 0.1),
        article_result(0.1, 0.8, 0.1, headline="Reliance Industries costs rise"),
        article_result(0.2, 0.2, 0.6, headline="Reliance Industries board meets"),
    ]
    summary, trend, warnings = aggregate_sentiment(articles, min_articles=3)
    assert summary.overall_label == "Neutral or mixed"
    assert summary.net_score == pytest.approx(0)
    assert summary.counts.total == 3
    assert (summary.counts.positive, summary.counts.negative, summary.counts.neutral) == (1, 1, 1)
    assert (summary.counts.positive_pct, summary.counts.negative_pct, summary.counts.neutral_pct) == (pytest.approx(100 / 3),) * 3
    assert summary.mean_probabilities.positive == pytest.approx(1.1 / 3)
    assert len(trend) == 1 and trend[0].article_count == 3
    assert not warnings


@pytest.mark.parametrize(
    ("score", "expected"),
    [(0.101, "Positive"), (0.1, "Neutral or mixed"), (-0.1, "Neutral or mixed"), (-0.101, "Negative")],
)
def test_overall_score_threshold_boundaries(score, expected):
    result = article_result((1 + score) / 2, (1 - score) / 2, 0)
    summary, _, _ = aggregate_sentiment([result], min_articles=1)
    assert summary.overall_label == expected


def test_empty_articles_do_not_create_neutral_zero_score():
    summary, trend, warnings = aggregate_sentiment([])
    assert summary.overall_label == "No eligible news"
    assert summary.net_score is None
    assert summary.mean_probabilities is None
    assert summary.counts.total == 0
    assert summary.counts.positive_pct is None
    assert trend == []
    assert warnings


def test_stock_catalog_includes_additional_nse_companies_and_avoids_short_alias_matches():
    stocks = list_stocks()
    assert len(stocks) == 250
    assert find_stock("ABB.NS", "NSE").company_name.startswith("ABB India")
    assert find_stock("SBIN", "NSE").company_name == "State Bank of India"
    assert find_stock("M&M.NS", "NSE").company_name.startswith("Mahindra")
    assert matches_company("ITC announces quarterly results", find_stock("ITC", "NSE"))
    assert not matches_company("Critical infrastructure update", find_stock("ITC", "NSE"))


def test_small_sample_is_insufficient_evidence():
    summary, _, warnings = aggregate_sentiment([article_result(0.8, 0.1, 0.1)], min_articles=3)
    assert summary.overall_label == "Insufficient evidence"
    assert summary.net_score == pytest.approx(0.7)
    assert warnings


def test_probabilities_validate_range_and_sum():
    with pytest.raises(ValidationError):
        Probabilities(positive=0.8, negative=0.8, neutral=0.0)
    with pytest.raises(ValidationError):
        Probabilities(positive=-0.1, negative=0.5, neutral=0.6)
    assert sum(Probabilities(positive=0.3, negative=0.2, neutral=0.5).model_dump().values()) == pytest.approx(1)


def test_duplicate_url_and_normalized_headline_are_removed():
    items = [
        news_article("Reliance Industries reports growth", "https://www.news.example/story?id=one&utm_source=feed"),
        news_article("Reliance Industries reports growth!", "https://another.example/copy"),
        news_article("Reliance Industries other update", "https://news.example/story-2?id=two"),
    ]
    filtered = deduplicate_and_filter(items, STOCK, 20)
    assert len(filtered) == 2
    assert filtered[0].url == "https://news.example/story?id=one"


def test_irrelevant_company_mention_is_filtered_and_description_can_be_missing():
    items = [
        news_article("Local school announces event", "https://news.example/irrelevant", "Local weather and school bulletin."),
        news_article("Reliance Industries shares update", "https://news.example/relevant", None),
    ]
    filtered = deduplicate_and_filter(items, STOCK, 10)
    assert [item.headline for item in filtered] == ["Reliance Industries shares update"]
    classified = classify_articles(filtered, DemoRuleClassifier(), NOW)
    assert classified[0].analyzed_headline_only
    assert classified[0].model_id == DemoRuleClassifier.model_id


def test_article_schema_preserves_publisher_date_source_probabilities():
    output = classify_articles([news_article()], DemoRuleClassifier(), NOW)[0]
    assert output.publisher == "Example News"
    assert str(output.url) == "https://news.example/story?id=1"
    assert output.published_at == NOW
    assert sum(output.probabilities.model_dump().values()) == pytest.approx(1)


def test_finbert_classifier_loads_once_and_returns_all_real_model_classes(monkeypatch):
    pipeline_calls = []
    inference_calls = []

    class FakePipeline:
        def __call__(self, texts, **kwargs):
            inference_calls.append((texts, kwargs))
            return [
                [
                    {"label": "positive", "score": 0.8},
                    {"label": "negative", "score": 0.1},
                    {"label": "neutral", "score": 0.1},
                ]
                for _ in texts
            ]

    def fake_pipeline(*args, **kwargs):
        pipeline_calls.append((args, kwargs))
        return FakePipeline()

    monkeypatch.setitem(sys.modules, "transformers", types.SimpleNamespace(pipeline=fake_pipeline))
    classifier = FinBertClassifier(Settings(finbert_model="ProsusAI/finbert"))
    first = classifier.classify(["financial headline"])
    second = classifier.classify(["another headline"])
    assert classifier.status == "loaded"
    assert len(pipeline_calls) == 1
    assert inference_calls[0][0] == ["financial headline"]
    assert first[0].label == SentimentLabel.positive
    assert first[0].probabilities.positive == pytest.approx(0.8)
    assert second[0].probabilities.neutral == pytest.approx(0.1)


def test_request_rejects_invalid_date_ranges_and_future_date():
    with pytest.raises(ValidationError):
        analyze_request(start_date=date(2026, 10, 21), end_date=date(2026, 10, 20))
    with pytest.raises(ValidationError):
        analyze_request(end_date=date.today().replace(year=date.today().year + 1))
    with pytest.raises(ValidationError, match="Start date cannot be in the future"):
        future = date.today() + timedelta(days=1)
        analyze_request(start_date=future, end_date=future)


def test_demo_mode_is_disabled_by_default():
    assert Settings().enable_demo_mode is False


def test_newsapi_defaults_to_a_30_day_local_maximum():
    assert Settings().news_max_age_days == 30


@pytest.mark.asyncio
async def test_news_api_authentication_and_rate_limit_errors_are_clear():
    settings = Settings(news_api_key="test-key")
    for status, expected in ((401, 502), (429, 429)):
        transport = httpx.MockTransport(lambda request, status=status: httpx.Response(status))
        async with httpx.AsyncClient(transport=transport) as client:
            provider = NewsApiProvider(settings, client)
            with pytest.raises(NewsProviderError) as error:
                await provider.search(STOCK, date(2026, 10, 15), date(2026, 10, 20), 10)
            assert error.value.status_code == expected


@pytest.mark.asyncio
async def test_news_api_explains_plan_limited_historical_dates():
    settings = Settings(news_api_key="test-key", news_max_age_days=30)
    provider = NewsApiProvider(settings)
    with pytest.raises(NewsProviderError, match="historical coverage") as error:
        await provider.search(STOCK, date(2026, 8, 1), date(2026, 8, 5), 10)
    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_news_api_allows_the_oldest_date_in_the_configured_30_day_window():
    calls = []

    def handler(request):
        calls.append(dict(request.url.params))
        return httpx.Response(200, json={"status": "ok", "totalResults": 0, "articles": []})

    settings = Settings(
        news_api_key="test-key",
        news_max_age_days=30,
        news_cache_ttl_seconds=0,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = NewsApiProvider(settings, client)
        start = date.today() - timedelta(days=29)
        end = date.today()
        articles, _, _, _ = await provider.search(STOCK, start, end, 10)

    assert articles == []
    assert len(calls) == 1
    assert calls[0]["from"] == start.isoformat()
    assert calls[0]["to"] == end.isoformat()


@pytest.mark.asyncio
async def test_news_api_rejects_dates_older_than_configured_30_day_window_without_request():
    settings = Settings(news_api_key="test-key", news_max_age_days=30)
    provider = NewsApiProvider(settings)
    with pytest.raises(NewsProviderError, match="only the most recent 30 days") as error:
        await provider.search(
            STOCK,
            date.today() - timedelta(days=30),
            date.today() - timedelta(days=29),
            10,
        )
    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_news_api_reports_missing_credentials_without_requesting_provider():
    provider = NewsApiProvider(Settings(news_api_key=""))
    with pytest.raises(NewsProviderError, match="NEWS_API_KEY is not configured") as error:
        await provider.search(STOCK, date(2026, 10, 20), date(2026, 10, 26), 10)
    assert error.value.status_code == 503


def gnews_article(title: str, url: str, description: str = "Reliance Industries market update.") -> dict:
    return {
        "title": title,
        "description": description,
        "source": {"name": "Business News"},
        "publishedAt": "2020-01-02T10:00:00Z",
        "url": url,
    }


@pytest.mark.asyncio
async def test_gnews_applies_historical_date_filters_and_deduplicates_across_pages():
    calls = []
    responses = [
        {
            "totalArticles": 4,
            "articles": [
                gnews_article(
                    "Reliance Industries shares rise",
                    "https://www.example.com/reliance?utm_source=feed",
                ),
                gnews_article(
                    "Reliance Industries shares rise!",
                    "https://another.example/reliance-copy",
                ),
            ],
        },
        {
            "totalArticles": 4,
            "articles": [
                gnews_article(
                    "Reliance Industries shares rise",
                    "https://example.com/reliance",
                ),
                gnews_article(
                    "Reliance Industries announces investment",
                    "https://example.com/investment",
                ),
            ],
        },
    ]

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=responses[len(calls) - 1])

    settings = Settings(
        news_provider="gnews",
        gnews_api_key="test-key",
        gnews_page_size=2,
        gnews_max_age_days=0,
        gnews_request_interval_seconds=0,
        news_cache_ttl_seconds=0,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GNewsProvider(settings, client)
        articles, cache_status, _, retrieved_count = await provider.search(
            STOCK, date(2020, 1, 1), date(2020, 1, 2), 4
        )

    assert len(calls) == 2
    assert [request.url.params["page"] for request in calls] == ["1", "2"]
    assert all(request.url.params["max"] == "2" for request in calls)
    assert calls[0].url.params["from"] == "2020-01-01T00:00:00Z"
    assert calls[0].url.params["to"] == "2020-01-02T23:59:59Z"
    assert calls[0].url.params["lang"] == "en"
    assert calls[0].headers["x-api-key"] == "test-key"
    assert "test-key" not in str(calls[0].url)
    assert cache_status == "disabled"
    assert retrieved_count == 4
    assert len(articles) == 2
    assert articles[0].url == "https://example.com/reliance"


@pytest.mark.asyncio
async def test_gnews_rejects_dates_outside_configured_historical_coverage():
    provider = GNewsProvider(
        Settings(news_provider="gnews", gnews_api_key="test-key", gnews_max_age_days=30)
    )
    with pytest.raises(NewsProviderError, match="only the most recent 30 days") as error:
        await provider.search(STOCK, date.today() - timedelta(days=90), date.today(), 10)
    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_gnews_rejects_dates_before_documented_archive_start():
    provider = GNewsProvider(
        Settings(news_provider="gnews", gnews_api_key="test-key", gnews_max_age_days=0)
    )
    with pytest.raises(NewsProviderError, match="2020-01-01") as error:
        await provider.search(STOCK, date(2019, 12, 31), date(2020, 1, 2), 10)
    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_gnews_reports_authentication_and_rate_limit_failures():
    settings = Settings(news_provider="gnews", gnews_api_key="test-key")
    for status, expected_status in ((401, 502), (429, 429)):
        transport = httpx.MockTransport(lambda _request, status=status: httpx.Response(status))
        async with httpx.AsyncClient(transport=transport) as client:
            provider = GNewsProvider(settings, client)
            with pytest.raises(NewsProviderError) as error:
                await provider.search(STOCK, date.today(), date.today(), 5)
        assert error.value.status_code == expected_status


def test_service_selects_gnews_only_when_explicitly_configured():
    service = SentimentService(Settings(news_provider="gnews"))
    assert isinstance(service.news_provider, GNewsProvider)


def test_finbert_load_failure_is_reported_without_heuristic_fallback(monkeypatch):
    def fail_pipeline(*_args, **_kwargs):
        raise OSError("model files unavailable")

    monkeypatch.setitem(sys.modules, "transformers", types.SimpleNamespace(pipeline=fail_pipeline))
    classifier = FinBertClassifier(Settings(finbert_model="ProsusAI/finbert"))
    with pytest.raises(ModelInferenceError, match="could not be loaded"):
        classifier.classify(["Reliance Industries reported results"])
    assert classifier.status == "error"


@pytest.mark.asyncio
async def test_news_api_timeout_returns_gateway_timeout_without_leaking_details():
    async def handler(_request):
        raise httpx.ReadTimeout("private transport detail")

    settings = Settings(news_api_key="test-key")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = NewsApiProvider(settings, client)
        with pytest.raises(NewsProviderError) as error:
            await provider.search(STOCK, date(2026, 10, 15), date(2026, 10, 20), 10)
    assert error.value.status_code == 504
    assert "private transport detail" not in str(error.value)


@pytest.mark.asyncio
async def test_provider_parses_filters_and_caches_provider_results():
    calls = []
    payload = {"status": "ok", "articles": [
        {
            "title": "Reliance Industries reports growth",
            "description": None,
            "source": {"name": "Business News"},
            "publishedAt": "2026-10-20T10:00:00Z",
            "url": "https://www.business.example/article?tracking=1",
        },
        {
            "title": "Local weather bulletin",
            "description": "A city forecast.",
            "source": {"name": "Local Desk"},
            "publishedAt": "2026-10-20T10:00:00Z",
            "url": "https://local.example/weather",
        },
    ]}

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=payload)

    settings = Settings(news_api_key="unit-test-secret", news_cache_ttl_seconds=60)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = NewsApiProvider(settings, client)
        first, first_status, fetched_at, retrieved_count = await provider.search(
            STOCK, date(2026, 10, 15), date(2026, 10, 20), 10
        )
        second, second_status, second_fetched_at, cached_retrieved_count = await provider.search(
            STOCK, date(2026, 10, 15), date(2026, 10, 20), 10
        )
    assert len(first) == 1
    assert first[0].description is None
    assert first[0].url == "https://business.example/article?tracking=1"
    assert first_status == "miss"
    assert second_status == "hit"
    assert fetched_at == second_fetched_at
    assert retrieved_count == cached_retrieved_count == 2
    assert len(calls) == 1
    assert calls[0].headers["x-api-key"] == "unit-test-secret"
    assert "unit-test-secret" not in str(calls[0].url)
    params = dict(calls[0].url.params)
    assert params["language"] == "en"
    assert params["page"] == "1"
    assert set(params["qInTitle"].split(" OR ")) == {
        '"Reliance Industries Ltd."',
        '"Reliance Industries"',
        '"RELIANCE"',
        '"RELIANCE.NS"',
        '"Reliance Industries Limited"',
        '"RIL"',
    }


@pytest.mark.asyncio
async def test_news_api_paginates_until_eligible_limit_is_filled():
    calls = []
    payloads = [
        {"status": "ok", "totalResults": 2, "articles": [{
            "title": "Unrelated market roundup",
            "description": "General market news.",
            "source": {"name": "Desk"},
            "publishedAt": "2026-10-20T10:00:00Z",
            "url": "https://news.example/unrelated",
        }]},
        {"status": "ok", "totalResults": 2, "articles": [{
            "title": "Reliance Industries reports growth",
            "description": "Company update.",
            "source": {"name": "Desk"},
            "publishedAt": "2026-10-20T10:00:00Z",
            "url": "https://news.example/reliance",
        }]},
    ]

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=payloads[len(calls) - 1])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = NewsApiProvider(Settings(news_api_key="unit-test-secret"), client)
        articles, _, _, retrieved_count = await provider.search(
            STOCK, date(2026, 10, 15), date(2026, 10, 20), 1
        )
    assert len(calls) == 2
    assert [request.url.params["page"] for request in calls] == ["1", "2"]
    assert retrieved_count == 2
    assert [article.headline for article in articles] == ["Reliance Industries reports growth"]


@pytest.mark.asyncio
async def test_service_empty_result_and_demo_mode_are_distinct():
    provider = FixedProvider([])
    service = SentimentService(
        Settings(news_api_key="configured", enable_demo_mode=True),
        news_provider=provider,
        classifier=FixedClassifier([]),
    )
    empty = await service.analyze(analyze_request())
    assert empty.sentiment.overall_label == "No eligible news"
    assert empty.sentiment.net_score is None
    assert empty.articles == []

    demo = await service.analyze(analyze_request(demo_mode=True))
    assert demo.source.mode == "demo"
    assert "synthetic" in demo.warnings[0].lower()
    assert demo.source.model_id == DemoRuleClassifier.model_id
    assert demo.articles
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_service_does_not_repeat_model_inference_for_unchanged_text():
    articles = [
        news_article("Reliance Industries reports growth", "https://news.example/a"),
        news_article("Reliance Industries expands business", "https://news.example/b"),
        news_article("Reliance Industries reports strong demand", "https://news.example/c"),
    ]
    classifier = FixedClassifier([(0.8, 0.1, 0.1)] * 3)
    provider = FixedProvider(articles)
    service = SentimentService(
        Settings(news_api_key="configured"),
        news_provider=provider,
        classifier=classifier,
    )
    request = analyze_request()
    first = await service.analyze(request)
    second = await service.analyze(request)
    assert classifier.calls == 1
    assert first.source.retrieved_at == second.source.retrieved_at
    assert first.source.cache_status == "miss"
    assert second.source.cache_status == "miss"


def test_api_contract_health_sources_stocks_and_request_validation():
    client = TestClient(app)
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert "news_configured" in health.json()
    assert "NEWS_API_KEY" not in health.text
    import app.main as api

    if api.settings.news_api_key:
        assert api.settings.news_api_key not in health.text
    assert client.get("/api/v1/stocks").status_code == 200
    sources = client.get("/api/v1/sentiment/sources")
    assert sources.status_code == 200
    if api.settings.news_api_key:
        assert api.settings.news_api_key not in sources.text
    invalid = client.post("/api/v1/sentiment/analyze", json={
        "symbol": "RELIANCE.NS",
        "exchange": "NSE",
        "start_date": "2026-10-20",
        "end_date": "2026-10-15",
        "max_articles": 10,
    })
    assert invalid.status_code == 422


def test_api_returns_empty_real_news_without_inventing_a_score(monkeypatch):
    import app.main as api

    settings = Settings(news_api_key="test-key")
    monkeypatch.setattr(api, "settings", settings)
    monkeypatch.setattr(
        api,
        "service",
        SentimentService(
            settings,
            news_provider=FixedProvider([]),
            classifier=FixedClassifier([]),
        ),
    )
    response = TestClient(app).post("/api/v1/sentiment/analyze", json={
        "symbol": "RELIANCE.NS",
        "exchange": "NSE",
        "start_date": (date.today() - timedelta(days=6)).isoformat(),
        "end_date": date.today().isoformat(),
        "max_articles": 10,
        "demo_mode": False,
    })

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"]["mode"] == "live"
    assert payload["sentiment"]["overall_label"] == "No eligible news"
    assert payload["sentiment"]["net_score"] is None
    assert payload["articles"] == []
    assert "test-key" not in response.text


def test_api_surfaces_newsapi_quota_failures_without_demo_fallback(monkeypatch):
    import app.main as api

    class QuotaLimitedProvider:
        name = "NewsAPI"

        async def search(self, *_args):
            raise NewsProviderError("News provider rate limit reached. Wait before trying again.", 429)

    settings = Settings(news_api_key="test-key")
    monkeypatch.setattr(api, "settings", settings)
    monkeypatch.setattr(
        api,
        "service",
        SentimentService(settings, news_provider=QuotaLimitedProvider()),
    )
    response = TestClient(app).post("/api/v1/sentiment/analyze", json={
        "symbol": "RELIANCE.NS",
        "exchange": "NSE",
        "start_date": (date.today() - timedelta(days=6)).isoformat(),
        "end_date": date.today().isoformat(),
        "max_articles": 10,
        "demo_mode": False,
    })

    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "news_provider_error"
    assert "rate limit" in response.json()["detail"]["message"]
    assert "articles" not in response.json()
    assert "test-key" not in response.text


def test_api_demo_response_matches_contract_and_warns_about_synthetic_news(monkeypatch):
    import app.main as api

    monkeypatch.setattr(
        api,
        "service",
        SentimentService(Settings(news_cache_ttl_seconds=0, enable_demo_mode=True)),
    )
    monkeypatch.setattr(api, "settings", Settings(enable_demo_mode=True))
    client = TestClient(app)
    response = client.post("/api/v1/sentiment/analyze", json={
        "symbol": "RELIANCE.NS",
        "exchange": "NSE",
        "start_date": "2026-10-20",
        "end_date": "2026-10-26",
        "max_articles": 10,
        "demo_mode": True,
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"]["mode"] == "demo"
    assert payload["sentiment"]["counts"]["total"] > 0
    assert payload["sentiment"]["overall_label"] == "Positive"
    assert payload["sentiment"]["net_score"] is not None
    assert all(".invalid/" in item["url"] for item in payload["articles"])
    assert all(item["source_provider"].startswith("Local demo") for item in payload["articles"])
    assert any("synthetic" in warning.lower() for warning in payload["warnings"])


def test_api_rejects_demo_mode_when_not_explicitly_enabled():
    client = TestClient(app)
    response = client.post("/api/v1/sentiment/analyze", json={
        "symbol": "RELIANCE.NS",
        "exchange": "NSE",
        "start_date": "2026-10-20",
        "end_date": "2026-10-26",
        "max_articles": 10,
        "demo_mode": True,
    })
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "demo_mode_disabled"


def test_api_returns_model_failure_instead_of_synthetic_predictions(monkeypatch):
    import app.main as api

    articles = [
        news_article("Reliance Industries reports results", "https://news.example/one"),
        news_article("Reliance Industries expands", "https://news.example/two"),
        news_article("Reliance Industries updates guidance", "https://news.example/three"),
    ]
    monkeypatch.setattr(
        api,
        "service",
        SentimentService(
            Settings(news_api_key="configured"),
            news_provider=FixedProvider(articles),
            classifier=FailedClassifier(),
        ),
    )
    client = TestClient(app)
    response = client.post("/api/v1/sentiment/analyze", json={
        "symbol": "RELIANCE.NS",
        "exchange": "NSE",
        "start_date": "2026-10-20",
        "end_date": "2026-10-26",
        "max_articles": 10,
        "demo_mode": False,
    })
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "model_inference_error"
    assert "articles" not in response.json()


def test_evidence_summary_links_representative_articles():
    source = article_result(0.8, 0.1, 0.1)
    summary = build_evidence_summary([source], "Insufficient evidence")
    assert summary.positive_themes[0].url == source.url
    assert "1 eligible" in summary.overview
    assert any("not a probability" in item for item in summary.limitations)
