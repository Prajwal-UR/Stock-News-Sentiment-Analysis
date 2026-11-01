export type Stock = {
  symbol: string
  exchange: 'NSE' | 'BSE'
  company_name: string
  aliases: string[]
}

export type Article = {
  headline: string
  description: string | null
  publisher: string
  published_at: string
  url: string
  sentiment: 'Positive' | 'Negative' | 'Neutral'
  probabilities: { positive: number; negative: number; neutral: number }
  article_score: number
  source_provider: string
  search_query: string
  model_id: string
  analyzed_at: string
  analyzed_headline_only: boolean
}

export type AnalyzeResult = {
  stock: Stock
  period: { start: string; end: string }
  source: {
    provider: string
    mode: 'live' | 'demo'
    retrieved_at: string
    analyzed_at: string
    cache_status: 'miss' | 'hit' | 'disabled' | 'demo'
    inference_cache_status: 'miss' | 'hit' | 'disabled' | 'demo'
    articles_retrieved: number
    articles_eligible: number
    model_id: string
  }
  sentiment: {
    overall_label: string
    net_score: number | null
    mean_probabilities: { positive: number; negative: number; neutral: number } | null
    counts: {
      total: number
      positive: number
      negative: number
      neutral: number
      positive_pct: number | null
      negative_pct: number | null
      neutral_pct: number | null
    }
  }
  trend: {
    date: string
    article_count: number
    mean_score: number
    positive: number
    negative: number
    neutral: number
  }[]
  articles: Article[]
  summary: {
    overview: string
    positive_themes: Evidence[]
    negative_themes: Evidence[]
    neutral_or_conflicting: Evidence[]
    limitations: string[]
  }
  warnings: string[]
}

export type Evidence = {
  text: string
  headline: string
  url: string
  sentiment: 'Positive' | 'Negative' | 'Neutral'
  article_score: number
}
