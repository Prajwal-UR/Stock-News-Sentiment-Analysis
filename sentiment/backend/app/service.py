from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone

from app.aggregation import aggregate_sentiment, build_evidence_summary
from app.cache import TTLCache, text_cache_key
from app.classifier import (
    Classification,
    DemoRuleClassifier,
    FinBertClassifier,
    ModelInferenceError,
    SentimentClassifier,
    classify_articles,
)
from app.config import Settings
from app.demo import demo_articles
from app.gnews import GNewsProvider
from app.news import NewsApiProvider, NewsProvider, NewsProviderError
from app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ArticleResult,
    SourceMetadata,
)
from app.stocks import find_stock


class SentimentService:
    def __init__(
        self,
        settings: Settings,
        news_provider: NewsProvider | None = None,
        classifier: SentimentClassifier | None = None,
        demo_classifier: SentimentClassifier | None = None,
    ) -> None:
        self.settings = settings
        self.news_provider = news_provider or self._configured_news_provider(settings)
        self.classifier = classifier or FinBertClassifier(settings)
        self.demo_classifier = demo_classifier or DemoRuleClassifier()
        self._classification_cache: TTLCache[list[Classification]] = TTLCache(
            settings.news_cache_ttl_seconds
        )
        self._classification_lock = asyncio.Lock()

    @staticmethod
    def _configured_news_provider(settings: Settings) -> NewsProvider:
        provider = settings.news_provider.casefold()
        if provider == "newsapi":
            return NewsApiProvider(settings)
        if provider == "gnews":
            return GNewsProvider(settings)
        raise ValueError(f"Unsupported NEWS_PROVIDER '{settings.news_provider}'. Choose newsapi or gnews.")

    async def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        stock = find_stock(request.symbol, request.exchange)
        if request.max_articles > self.settings.max_articles_per_request:
            raise ValueError(
                f"Maximum article count is {self.settings.max_articles_per_request}."
            )
        if request.demo_mode:
            if not self.settings.demo_mode_available:
                raise NewsProviderError(
                    "Demo mode is disabled. Configure ENABLE_DEMO_MODE=true only in a development or test environment.",
                    403,
                )
            news = demo_articles(stock, request.start_date, request.end_date, request.max_articles)
            articles_retrieved = len(news)
            provider_name = "Local demo fixtures (synthetic; not real news)"
            cache_status = "demo"
            retrieved_at = datetime.now(timezone.utc)
            classifier = self.demo_classifier
            inference_cache_status = "demo"
        else:
            news, cache_status, retrieved_at, articles_retrieved = await self.news_provider.search(
                stock, request.start_date, request.end_date, request.max_articles
            )
            provider_name = self.news_provider.name
            classifier = self.classifier

        texts = [
            f"{article.headline}. {article.description}" if article.description else article.headline
            for article in news
        ]
        key = text_cache_key(classifier.model_id, [text[:3000] for text in texts])
        cached_predictions = self._classification_cache.get(key) if texts else None
        if cached_predictions is not None:
            predictions = cached_predictions
            inference_cache_status = "hit"
        elif news:
            async with self._classification_lock:
                cached_predictions = self._classification_cache.get(key)
                if cached_predictions is None:
                    try:
                        article_results = await asyncio.to_thread(
                            classify_articles, news, classifier, datetime.now(timezone.utc)
                        )
                    except ModelInferenceError:
                        raise
                    except RuntimeError as exc:
                        raise ModelInferenceError(str(exc)) from exc
                    predictions = [
                        Classification(label=item.sentiment, probabilities=item.probabilities)
                        for item in article_results
                    ]
                    self._classification_cache.set(key, predictions)
                    inference_cache_status = "miss" if self.settings.news_cache_ttl_seconds else "disabled"
                else:
                    predictions = cached_predictions
                    inference_cache_status = "hit"
        else:
            predictions = []
            inference_cache_status = "disabled" if not self.settings.news_cache_ttl_seconds else "miss"

        if news:
            analyzed_at = datetime.now(timezone.utc)
            articles = [
                ArticleResult(
                    headline=article.headline,
                    description=article.description,
                    publisher=article.publisher,
                    published_at=article.published_at,
                    url=article.url,
                    sentiment=prediction.label,
                    probabilities=prediction.probabilities,
                    article_score=prediction.probabilities.positive - prediction.probabilities.negative,
                    source_provider=article.source_provider,
                    search_query=article.search_query,
                    model_id=classifier.model_id,
                    analyzed_at=analyzed_at,
                    analyzed_headline_only=article.description is None,
                )
                for article, prediction in zip(news, predictions, strict=True)
            ]
        else:
            articles = []

        sentiment, trend, warnings = aggregate_sentiment(
            articles, self.settings.min_articles_for_conclusion
        )
        summary = build_evidence_summary(articles, sentiment.overall_label)
        if request.demo_mode:
            warnings.insert(0, "DEMO MODE: all articles are synthetic local fixtures and are not real news.")
        elif not self.settings.news_available:
            warnings.append("Configure NEWS_API_KEY to retrieve real provider articles.")
        return AnalyzeResponse(
            stock=stock,
            period={"start": request.start_date, "end": request.end_date},
            source=SourceMetadata(
                provider=provider_name,
                mode="demo" if request.demo_mode else "live",
                retrieved_at=retrieved_at,
                analyzed_at=datetime.now(timezone.utc),
                cache_status=cache_status,
                inference_cache_status=inference_cache_status,
                articles_retrieved=articles_retrieved,
                articles_eligible=len(news),
                model_id=classifier.model_id,
            ),
            sentiment=sentiment,
            trend=trend,
            articles=articles,
            summary=summary,
            warnings=warnings,
        )
