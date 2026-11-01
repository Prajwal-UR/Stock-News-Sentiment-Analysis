from __future__ import annotations

from datetime import date, datetime, time, timezone

from app.news import NewsArticle, deduplicate_and_filter
from app.schemas import StockItem


def demo_articles(stock: StockItem, start_date: date, end_date: date, limit: int) -> list[NewsArticle]:
    templates = [
        ("{name} reports quarterly revenue growth, shares open higher", "The company reported revenue growth in its latest quarterly update.", "Market Desk", "positive"),
        ("Analysts note {name} expansion and demand outlook", "The report describes company expansion and demand trends.", "Business Journal", "positive"),
        ("Investors weigh costs after {name} quarterly results", "Higher costs were discussed alongside the company's results.", "Financial Review", "negative"),
        ("{name} board reviews investment and capital allocation plan", "The company described capital allocation for the current period.", "India Markets", "neutral"),
        ("Market coverage: {name} faces mixed analyst outlook", "The article notes a mix of positive growth and cost considerations.", "Equity Monitor", "neutral"),
    ]
    days = [start_date] if start_date == end_date else [start_date, start_date, end_date, end_date, end_date]
    results = []
    for index, (headline_template, description, publisher, _) in enumerate(templates[:limit]):
        published_date = days[index % len(days)]
        headline = headline_template.format(name=stock.company_name)
        safe_symbol = stock.symbol.replace(".", "-").lower()
        results.append(
            NewsArticle(
                headline=headline,
                description=description.format(name=stock.company_name),
                publisher=publisher,
                published_at=datetime.combine(published_date, time(9 + index, 15), tzinfo=timezone.utc),
                url=f"https://demo.stockq.invalid/news/{safe_symbol}-{index + 1}",
                source_provider="Local demo fixtures (synthetic; not real news)",
                search_query=stock.company_name,
            )
        )
    return deduplicate_and_filter(results, stock, limit)
