from __future__ import annotations

from collections import defaultdict

from app.schemas import (
    ArticleResult,
    EvidenceItem,
    EvidenceSummary,
    SentimentCounts,
    SentimentLabel,
    SentimentSummary,
    TrendPoint,
)


def aggregate_sentiment(
    articles: list[ArticleResult], min_articles: int = 3
) -> tuple[SentimentSummary, list[TrendPoint], list[str]]:
    total = len(articles)
    counts_by_label = {
        label: sum(article.sentiment == label for article in articles)
        for label in SentimentLabel
    }
    if total:
        percentages = {
            label: counts_by_label[label] / total * 100
            for label in SentimentLabel
        }
        mean_probabilities = {
            field: sum(getattr(article.probabilities, field) for article in articles) / total
            for field in ("positive", "negative", "neutral")
        }
        score = sum(article.article_score for article in articles) / total
        threshold_score = round(score, 12)
        if total < min_articles:
            overall_label = "Insufficient evidence"
        elif threshold_score > 0.10:
            overall_label = "Positive"
        elif threshold_score < -0.10:
            overall_label = "Negative"
        else:
            overall_label = "Neutral or mixed"
        probabilities = {
            "positive": mean_probabilities["positive"],
            "negative": mean_probabilities["negative"],
            "neutral": mean_probabilities["neutral"],
        }
        positive_pct = percentages[SentimentLabel.positive]
        negative_pct = percentages[SentimentLabel.negative]
        neutral_pct = percentages[SentimentLabel.neutral]
    else:
        score = None
        overall_label = "No eligible news"
        probabilities = None
        positive_pct = negative_pct = neutral_pct = None

    summary = SentimentSummary(
        overall_label=overall_label,
        net_score=score,
        mean_probabilities=probabilities,
        counts=SentimentCounts(
            total=total,
            positive=counts_by_label[SentimentLabel.positive],
            negative=counts_by_label[SentimentLabel.negative],
            neutral=counts_by_label[SentimentLabel.neutral],
            positive_pct=positive_pct,
            negative_pct=negative_pct,
            neutral_pct=neutral_pct,
        ),
    )

    daily: dict[object, list[ArticleResult]] = defaultdict(list)
    for article in articles:
        daily[article.published_at.date()].append(article)
    trend = []
    for publication_date, day_articles in sorted(daily.items()):
        trend.append(
            TrendPoint(
                date=publication_date,
                article_count=len(day_articles),
                mean_score=sum(item.article_score for item in day_articles) / len(day_articles),
                positive=sum(item.sentiment == SentimentLabel.positive for item in day_articles),
                negative=sum(item.sentiment == SentimentLabel.negative for item in day_articles),
                neutral=sum(item.sentiment == SentimentLabel.neutral for item in day_articles),
            )
        )
    warnings = []
    if total == 0:
        warnings.append("No eligible, unique company news articles were found for this period.")
    elif total < min_articles:
        warnings.append(
            f"Only {total} eligible article(s) were analyzed; at least {min_articles} are required for an overall sentiment conclusion."
        )
    return summary, trend, warnings


def build_evidence_summary(articles: list[ArticleResult], overall_label: str) -> EvidenceSummary:
    def evidence(item: ArticleResult) -> EvidenceItem:
        return EvidenceItem(
            text=f"{item.sentiment.value} model label; article score {item.article_score:+.3f}.",
            headline=item.headline,
            url=item.url,
            sentiment=item.sentiment,
            article_score=item.article_score,
        )

    positive = [item for item in articles if item.sentiment == SentimentLabel.positive]
    negative = [item for item in articles if item.sentiment == SentimentLabel.negative]
    neutral = [item for item in articles if item.sentiment == SentimentLabel.neutral]
    ordered_positive = sorted(positive, key=lambda item: item.article_score, reverse=True)[:3]
    ordered_negative = sorted(negative, key=lambda item: item.article_score)[:3]
    date_values = sorted(item.published_at.date() for item in articles)
    if not articles:
        overview = "No conclusion is available because no eligible, unique articles were analyzed."
    elif len(articles) < 3:
        overview = (
            f"{len(articles)} eligible article(s) were analyzed. Evidence is insufficient for a reliable overall conclusion."
        )
    else:
        overview = (
            f"The equal-weight mean article score is {sum(item.article_score for item in articles) / len(articles):+.3f} "
            f"({overall_label}) across {len(articles)} eligible unique articles published "
            f"{date_values[0]} through {date_values[-1]}. This describes model classifications of retrieved headlines/descriptions, not expected share returns."
        )
    limitations = [
        "Article sentiment is not a probability of future share-price movement and is not investment advice.",
        "The provider may return headlines and short descriptions only; full article text is not inferred or stored.",
        "Syndicated copies are deduplicated by canonical URL and normalized headline; unique URLs are not necessarily independent reporting.",
        "Company-name and alias matching is a transparent filter and may omit or misclassify ambiguous mentions.",
        "Classification probabilities are model outputs, not calibrated measures of investment certainty.",
    ]
    if any(item.analyzed_headline_only for item in articles):
        limitations.append("Some articles had no description; those articles were classified using the headline only.")
    return EvidenceSummary(
        overview=overview,
        positive_themes=[evidence(item) for item in ordered_positive],
        negative_themes=[evidence(item) for item in ordered_negative],
        neutral_or_conflicting=[evidence(item) for item in (neutral[:3] + positive[3:4] + negative[3:4])],
        limitations=limitations,
    )
