from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from app.config import Settings
from app.news import NewsArticle
from app.schemas import ArticleResult, Probabilities, SentimentLabel

FINBERT_LABELS = ("positive", "negative", "neutral")


class ModelInferenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class Classification:
    label: SentimentLabel
    probabilities: Probabilities


class SentimentClassifier(Protocol):
    model_id: str

    def classify(self, texts: list[str]) -> list[Classification]: ...


class FinBertClassifier:
    def __init__(self, settings: Settings) -> None:
        self.model_id = settings.finbert_model
        self._pipeline = None
        self._load_lock = threading.Lock()
        self._status = "not_loaded"
        self._status_lock = threading.Lock()

    @property
    def status(self) -> str:
        with self._status_lock:
            return self._status

    def _get_pipeline(self):
        if self._pipeline is None:
            with self._load_lock:
                if self._pipeline is None:
                    with self._status_lock:
                        self._status = "loading"
                    try:
                        from transformers import pipeline

                        self._pipeline = pipeline(
                            "text-classification",
                            model=self.model_id,
                            tokenizer=self.model_id,
                            top_k=None,
                            truncation=True,
                            max_length=512,
                            device=-1,
                        )
                    except Exception as exc:
                        with self._status_lock:
                            self._status = "error"
                        reason = str(exc).strip()
                        details = f" Details: {reason[:300]}" if reason else ""
                        raise ModelInferenceError(
                            f"FinBERT model '{self.model_id}' could not be loaded. "
                            f"Install backend requirements and ensure the model can be downloaded.{details}"
                        ) from exc
                    with self._status_lock:
                        self._status = "loaded"
        return self._pipeline

    def classify(self, texts: list[str]) -> list[Classification]:
        if not texts:
            return []
        pipeline_instance = self._get_pipeline()
        try:
            results = pipeline_instance(texts, batch_size=8, truncation=True, max_length=512)
        except Exception as exc:
            raise ModelInferenceError(
                f"FinBERT inference failed for model '{self.model_id}'."
            ) from exc
        classifications = []
        for result in results:
            values = {str(item["label"]).casefold(): float(item["score"]) for item in result}
            probabilities = Probabilities(
                positive=values.get("positive", 0),
                negative=values.get("negative", 0),
                neutral=values.get("neutral", 0),
            )
            top_label = max(
                FINBERT_LABELS,
                key=lambda label: getattr(probabilities, label),
            )
            classifications.append(
                Classification(
                    label=SentimentLabel(top_label.capitalize()),
                    probabilities=probabilities,
                )
            )
        return classifications


class DemoRuleClassifier:
    model_id = "StockQ demo heuristic (not FinBERT)"
    POSITIVE_WORDS = {"growth", "higher", "expansion", "beat", "profit", "strong"}
    NEGATIVE_WORDS = {"cost", "decline", "loss", "lower", "weak", "risk"}

    def classify(self, texts: list[str]) -> list[Classification]:
        results = []
        for text in texts:
            words = set(re.findall(r"[a-z]+", text.casefold()))
            positive = len(words & self.POSITIVE_WORDS)
            negative = len(words & self.NEGATIVE_WORDS)
            if positive > negative:
                values = (0.78, 0.08, 0.14)
            elif negative > positive:
                values = (0.08, 0.78, 0.14)
            else:
                values = (0.10, 0.10, 0.80)
            probabilities = Probabilities(
                positive=values[0], negative=values[1], neutral=values[2]
            )
            label = max(
                FINBERT_LABELS,
                key=lambda item: getattr(probabilities, item),
            )
            results.append(
                Classification(
                    label=SentimentLabel(label.capitalize()),
                    probabilities=probabilities,
                )
            )
        return results


def classify_articles(
    articles: list[NewsArticle],
    classifier: SentimentClassifier,
    analyzed_at: datetime | None = None,
) -> list[ArticleResult]:
    if not articles:
        return []
    timestamp = analyzed_at or datetime.now(timezone.utc)
    texts = [
        f"{article.headline}. {article.description}" if article.description else article.headline
        for article in articles
    ]
    predictions = classifier.classify([text[:3000] for text in texts])
    if len(predictions) != len(articles):
        raise RuntimeError("Sentiment classifier returned an unexpected number of predictions.")
    result = []
    for article, classification in zip(articles, predictions, strict=True):
        probabilities = classification.probabilities
        result.append(
            ArticleResult(
                headline=article.headline,
                description=article.description,
                publisher=article.publisher,
                published_at=article.published_at,
                url=article.url,
                sentiment=classification.label,
                probabilities=probabilities,
                article_score=probabilities.positive - probabilities.negative,
                source_provider=article.source_provider,
                search_query=article.search_query,
                model_id=classifier.model_id,
                analyzed_at=timestamp,
                analyzed_headline_only=article.description is None,
            )
        )
    return result
