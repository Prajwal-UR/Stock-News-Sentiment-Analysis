from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class SentimentLabel(str, Enum):
    positive = "Positive"
    negative = "Negative"
    neutral = "Neutral"


class StockItem(BaseModel):
    symbol: str
    exchange: Literal["NSE", "BSE"]
    company_name: str
    aliases: list[str]


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    symbol: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9.&_-]+$")
    exchange: Literal["NSE", "BSE"]
    start_date: date
    end_date: date
    max_articles: int = Field(default=30, ge=1, le=100)
    demo_mode: bool = False

    @model_validator(mode="after")
    def validate_period(self) -> AnalyzeRequest:
        if self.end_date < self.start_date:
            raise ValueError("End date must be on or after start date.")
        if self.start_date > date.today():
            raise ValueError("Start date cannot be in the future.")
        if self.end_date > date.today():
            raise ValueError("End date cannot be in the future.")
        if (self.end_date - self.start_date).days > 365 and self.demo_mode:
            raise ValueError("Demo mode supports date ranges up to one year.")
        return self


class Probabilities(BaseModel):
    positive: float = Field(ge=0, le=1)
    negative: float = Field(ge=0, le=1)
    neutral: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def probabilities_sum_to_one(self) -> Probabilities:
        if abs(self.positive + self.negative + self.neutral - 1) > 0.01:
            raise ValueError("Sentiment probabilities must sum to approximately 1.")
        return self


class ArticleResult(BaseModel):
    headline: str
    description: str | None
    publisher: str
    published_at: datetime
    url: HttpUrl
    sentiment: SentimentLabel
    probabilities: Probabilities
    article_score: float = Field(ge=-1, le=1)
    source_provider: str
    search_query: str
    model_id: str
    analyzed_at: datetime
    analyzed_headline_only: bool


class SentimentCounts(BaseModel):
    total: int = Field(ge=0)
    positive: int = Field(ge=0)
    negative: int = Field(ge=0)
    neutral: int = Field(ge=0)
    positive_pct: float | None = Field(default=None, ge=0, le=100)
    negative_pct: float | None = Field(default=None, ge=0, le=100)
    neutral_pct: float | None = Field(default=None, ge=0, le=100)


class TrendPoint(BaseModel):
    date: date
    article_count: int = Field(ge=1)
    mean_score: float = Field(ge=-1, le=1)
    positive: int = Field(ge=0)
    negative: int = Field(ge=0)
    neutral: int = Field(ge=0)


class SourceMetadata(BaseModel):
    provider: str
    mode: Literal["live", "demo"]
    retrieved_at: datetime
    analyzed_at: datetime
    cache_status: Literal["miss", "hit", "disabled", "demo"]
    inference_cache_status: Literal["miss", "hit", "disabled", "demo"]
    articles_retrieved: int = Field(ge=0)
    articles_eligible: int = Field(ge=0)
    model_id: str


class SentimentSummary(BaseModel):
    overall_label: str
    net_score: float | None = Field(default=None, ge=-1, le=1)
    mean_probabilities: Probabilities | None = None
    counts: SentimentCounts


class EvidenceItem(BaseModel):
    text: str
    headline: str
    url: HttpUrl
    sentiment: SentimentLabel
    article_score: float


class EvidenceSummary(BaseModel):
    overview: str
    positive_themes: list[EvidenceItem]
    negative_themes: list[EvidenceItem]
    neutral_or_conflicting: list[EvidenceItem]
    limitations: list[str]


class AnalyzeResponse(BaseModel):
    stock: StockItem
    period: dict[str, date]
    source: SourceMetadata
    sentiment: SentimentSummary
    trend: list[TrendPoint]
    articles: list[ArticleResult]
    summary: EvidenceSummary
    warnings: list[str]
