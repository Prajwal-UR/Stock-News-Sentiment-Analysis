import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import App from './App'
import * as api from './api'
import StockLogo from './StockLogo'
import type { AnalyzeResult } from './types'

vi.mock('./api', () => ({
  getStocks: vi.fn(),
  getSources: vi.fn(),
  analyzeSentiment: vi.fn(),
}))

afterEach(() => {
  cleanup()
  vi.unstubAllEnvs()
})

const stocks = [{
  symbol: 'RELIANCE.NS',
  exchange: 'NSE' as const,
  company_name: 'Reliance Industries',
  aliases: ['Reliance Industries', 'RIL'],
}]

const response: AnalyzeResult = {
  stock: stocks[0],
  period: { start: '2026-10-01', end: '2026-10-08' },
  source: {
    provider: 'NewsAPI',
    mode: 'live',
    retrieved_at: '2026-10-08T10:00:00Z',
    analyzed_at: '2026-10-08T10:01:00Z',
    cache_status: 'miss',
    inference_cache_status: 'miss',
    articles_retrieved: 4,
    articles_eligible: 1,
    model_id: 'ProsusAI/finbert',
  },
  sentiment: {
    overall_label: 'Insufficient evidence',
    net_score: 0.7,
    mean_probabilities: { positive: 0.8, negative: 0.1, neutral: 0.1 },
    counts: { total: 1, positive: 1, negative: 0, neutral: 0, positive_pct: 100, negative_pct: 0, neutral_pct: 0 },
  },
  trend: [{ date: '2026-10-08', article_count: 1, mean_score: 0.7, positive: 1, negative: 0, neutral: 0 }],
  articles: [{
    headline: 'Reliance Industries reports quarterly growth',
    description: 'Available provider description.',
    publisher: 'Market Desk',
    published_at: '2026-10-08T09:00:00Z',
    url: 'https://news.example.test/article',
    sentiment: 'Positive',
    probabilities: { positive: 0.8, negative: 0.1, neutral: 0.1 },
    article_score: 0.7,
    source_provider: 'NewsAPI',
    search_query: '"Reliance Industries"',
    model_id: 'ProsusAI/finbert',
    analyzed_at: '2026-10-08T10:00:00Z',
    analyzed_headline_only: false,
  }],
  summary: {
    overview: 'One article; insufficient evidence.',
    positive_themes: [{
      text: 'Positive label.',
      headline: 'Reliance Industries reports quarterly growth',
      url: 'https://news.example.test/article',
      sentiment: 'Positive',
      article_score: 0.7,
    }],
    negative_themes: [],
    neutral_or_conflicting: [],
    limitations: ['Provider headlines only.'],
  },
  warnings: [],
}

describe('stock logo', () => {
  it('renders a deterministic monogram when no Logo.dev key is configured', () => {
    vi.stubEnv('VITE_LOGO_DEV_PUBLISHABLE_KEY', '')
    render(<StockLogo stock={stocks[0]} />)
    expect(document.querySelector('.stock-logo svg')).toBeInTheDocument()
    expect(document.querySelector('.stock-logo text')).toHaveTextContent('RI')
    expect(document.querySelector('.stock-logo img')).not.toBeInTheDocument()
    expect(document.querySelector('.stock-logo')).toHaveAttribute('aria-hidden', 'true')
  })

  it('loads the ticker logo and falls back to initials when it fails', () => {
    vi.stubEnv('VITE_LOGO_DEV_PUBLISHABLE_KEY', 'publishable-test-key')
    render(<StockLogo stock={stocks[0]} />)
    const image = document.querySelector('.stock-logo img')
    if (!(image instanceof HTMLImageElement)) {
      throw new Error('Logo.dev image was not rendered.')
    }
    expect(image).toHaveAttribute(
      'src',
      'https://img.logo.dev/ticker/RELIANCE.NS?token=publishable-test-key&size=64&format=png',
    )
    fireEvent.error(image)
    expect(document.querySelector('.stock-logo text')).toHaveTextContent('RI')
    expect(document.querySelector('.stock-logo img')).not.toBeInTheDocument()
  })
})

describe('sentiment dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.getStocks).mockResolvedValue(stocks)
    vi.mocked(api.getSources).mockResolvedValue({
      providers: [{ name: 'NewsAPI', configured: false, availability: 'NEWS_API_KEY required' }],
      model: 'ProsusAI/finbert',
      model_status: 'not_loaded',
      demo_mode_available: false,
      max_age_days: 30,
    })
  })

  it('defaults to real analysis and renders provider response metrics and source link', async () => {
    vi.mocked(api.analyzeSentiment).mockResolvedValue(response)
    render(<App />)
    expect(screen.queryByRole('link', { name: 'Stock News Sentiment Analysis home' })).not.toBeInTheDocument()
    const pageLogo = screen.getByRole('img', { name: 'Stock News Sentiment Analysis' })
    expect(pageLogo).toHaveAttribute('src', '/stockq-market-logo.png')
    expect(pageLogo.closest('.sentiment-page-header')).toBeInTheDocument()
    expect(screen.queryByText(/NewsAPI · configured/)).not.toBeInTheDocument()
    await screen.findByText('Reliance Industries · NSE · RELIANCE.NS')
    expect(screen.queryByRole('checkbox', { name: 'Use demo fixtures' })).not.toBeInTheDocument()
    expect(screen.getByText(/obtain an API key at/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Analyze sentiment' }))

    expect(await screen.findByText('Insufficient evidence')).toBeInTheDocument()
    const articleLinks = screen.getAllByRole('link', { name: /Reliance Industries reports quarterly growth/ })
    expect(articleLinks.some((link) => link.getAttribute('href') === 'https://news.example.test/article')).toBe(true)
    expect(api.analyzeSentiment).toHaveBeenCalledWith(expect.objectContaining({
      symbol: 'RELIANCE.NS',
      exchange: 'NSE',
      max_articles: 30,
      demo_mode: false,
    }))
    expect(screen.getByRole('region', { name: 'Article inclusion' })).toHaveTextContent('FETCHED FROM PROVIDER')
    expect(screen.getByRole('region', { name: 'Article inclusion' })).toHaveTextContent('4')
    expect(screen.getByRole('region', { name: 'Article inclusion' })).toHaveTextContent('ELIGIBLE & ANALYZED')
    expect(screen.getByRole('region', { name: 'Article inclusion' })).toHaveTextContent('1')
    expect(screen.getByRole('region', { name: 'Article inclusion' })).toHaveTextContent('FETCHED, NOT ANALYZED')
    expect(screen.getByText('Included in sentiment')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Stock News Sentiment Analysis' })).toBeInTheDocument()
  })

  it('validates unsupported stock selection before making a request', async () => {
    render(<App />)
    const input = await screen.findByRole('combobox', { name: 'Company or ticker' })
    fireEvent.change(input, { target: { value: 'Unknown Co' } })
    fireEvent.click(screen.getByRole('button', { name: 'Analyze sentiment' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Choose a supported company')
    expect(api.analyzeSentiment).not.toHaveBeenCalled()
  })

  it('defaults to 30 days and supports preset and custom date ranges', async () => {
    vi.mocked(api.getSources).mockResolvedValue({
      providers: [{ name: 'NewsAPI', configured: true, availability: 'configured' }],
      model: 'ProsusAI/finbert',
      model_status: 'not_loaded',
      demo_mode_available: false,
      max_age_days: 30,
    })
    render(<App />)
    await screen.findByText('Reliance Industries · NSE · RELIANCE.NS')

    const range = screen.getByRole('button', { name: 'Date range' })
    const start = screen.getByLabelText('Start date') as HTMLInputElement
    const end = screen.getByLabelText('End date') as HTMLInputElement
    expect(range).toHaveTextContent('Last 30 Days')

    const expectedStart = (days: number) => {
      const value = new Date(`${end.value}T00:00:00Z`)
      value.setUTCDate(value.getUTCDate() - days + 1)
      return value.toISOString().slice(0, 10)
    }
    expect(start.value).toBe(expectedStart(30))
    expect(start.min).toBe(expectedStart(30))
    fireEvent.click(range)
    expect(screen.getByRole('listbox', { name: 'Date range options' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('option', { name: /Last 7 Days/ }))
    expect(start.value).toBe(expectedStart(7))
    fireEvent.click(range)
    fireEvent.click(screen.getByRole('option', { name: /Custom date range/ }))
    const customEnd = new Date(`${end.value}T00:00:00Z`)
    const customStart = new Date(customEnd)
    customStart.setUTCDate(customEnd.getUTCDate() - 13)
    fireEvent.change(start, { target: { value: customStart.toISOString().slice(0, 10) } })
    fireEvent.change(end, { target: { value: customEnd.toISOString().slice(0, 10) } })
    expect(range).toHaveTextContent('Custom date range')
    expect(start).toHaveValue(customStart.toISOString().slice(0, 10))
    expect(end).toHaveValue(customEnd.toISOString().slice(0, 10))
  })

  it('uses the themed maximum-articles picker and submits the selected limit', async () => {
    vi.mocked(api.analyzeSentiment).mockResolvedValue(response)
    render(<App />)
    await screen.findByText('Reliance Industries · NSE · RELIANCE.NS')

    const limit = screen.getByRole('button', { name: 'Maximum articles' })
    expect(limit).toHaveTextContent('30 articles')
    fireEvent.keyDown(limit, { key: 'Enter' })
    expect(screen.getByRole('listbox', { name: 'Maximum article options' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('option', { name: /50 articles/ }))
    expect(limit).toHaveTextContent('50 articles')

    fireEvent.click(screen.getByRole('button', { name: 'Analyze sentiment' }))
    await screen.findByText('Insufficient evidence')
    expect(api.analyzeSentiment).toHaveBeenCalledWith(expect.objectContaining({ max_articles: 50 }))
  })

  it('rejects future dates in the form before calling the API', async () => {
    render(<App />)
    await screen.findByText('Reliance Industries · NSE · RELIANCE.NS')
    const start = screen.getByLabelText('Start date')
    const end = screen.getByLabelText('End date')
    const todayValue = (end as HTMLInputElement).value
    const futureDate = new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10)
    fireEvent.change(start, { target: { value: futureDate } })
    fireEvent.change(end, { target: { value: futureDate } })
    fireEvent.submit(start.closest('form')!)
    expect(await screen.findByRole('alert')).toHaveTextContent('cannot be in the future')
    expect(api.analyzeSentiment).not.toHaveBeenCalled()

    const previousDay = new Date(`${todayValue}T00:00:00Z`)
    previousDay.setUTCDate(previousDay.getUTCDate() - 1)
    fireEvent.change(start, { target: { value: todayValue } })
    fireEvent.change(end, { target: { value: previousDay.toISOString().slice(0, 10) } })
    fireEvent.submit(start.closest('form')!)
    expect(await screen.findByRole('alert')).toHaveTextContent('End date must be on or after start date')
    expect(api.analyzeSentiment).not.toHaveBeenCalled()
  })

  it('uses the themed stock picker with keyboard navigation and selection', async () => {
    const infosys: typeof stocks[number] = {
      symbol: 'INFY.NS',
      exchange: 'NSE',
      company_name: 'Infosys',
      aliases: ['Infosys', 'INFY'],
    }
    vi.mocked(api.getStocks).mockResolvedValue([...stocks, infosys])
    vi.mocked(api.analyzeSentiment).mockResolvedValue({
      ...response,
      stock: infosys,
    })
    render(<App />)
    const input = await screen.findByRole('combobox', { name: 'Company or ticker' })
    fireEvent.focus(input)
    fireEvent.change(input, { target: { value: 'Info' } })
    expect(screen.getByRole('listbox', { name: 'Available stocks' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /INFY\.NS Infosys NSE/ })).toBeInTheDocument()
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(input).toHaveValue('INFY.NS')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Analyze sentiment' }))
    await screen.findByText('Infosys · NSE · INFY.NS')
    expect(api.analyzeSentiment).toHaveBeenCalledWith(expect.objectContaining({
      symbol: 'INFY.NS',
      exchange: 'NSE',
    }))
  })

  it('shows backend errors and exits loading state', async () => {
    vi.mocked(api.analyzeSentiment).mockRejectedValue(new Error('News provider rate limit reached. Wait before trying again.'))
    render(<App />)
    await screen.findByText('Reliance Industries · NSE · RELIANCE.NS')
    fireEvent.click(screen.getByRole('button', { name: 'Analyze sentiment' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('News provider rate limit reached')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Analyze sentiment' })).toBeEnabled())
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })

  it('offers demo fixtures only when the backend explicitly enables development mode', async () => {
    vi.mocked(api.getSources).mockResolvedValue({
      providers: [{ name: 'NewsAPI', configured: false, availability: 'NEWS_API_KEY required' }],
      model: 'ProsusAI/finbert',
      model_status: 'not_loaded',
      demo_mode_available: true,
      max_age_days: 30,
    })
    vi.mocked(api.analyzeSentiment).mockResolvedValue({ ...response, source: { ...response.source, mode: 'demo', provider: 'Local demo fixtures' } })
    render(<App />)
    const checkbox = await screen.findByRole('checkbox', { name: 'Use demo fixtures' })
    expect(checkbox).not.toBeChecked()
    fireEvent.click(checkbox)
    fireEvent.click(screen.getByRole('button', { name: 'Analyze sentiment' }))
    await waitFor(() => expect(api.analyzeSentiment).toHaveBeenCalledWith(expect.objectContaining({ demo_mode: true })))
  })

  it('shows an accessible loading state while a request is pending', async () => {
    let finishRequest!: (value: AnalyzeResult) => void
    vi.mocked(api.analyzeSentiment).mockReturnValue(new Promise((resolve) => { finishRequest = resolve }))
    render(<App />)
    await screen.findByText('Reliance Industries · NSE · RELIANCE.NS')
    fireEvent.click(screen.getByRole('button', { name: 'Analyze sentiment' }))
    expect(screen.getByRole('status')).toHaveTextContent('Retrieving provider news')
    expect(screen.getByRole('button', { name: 'Analyzing…' })).toBeDisabled()
    expect(screen.getByRole('status').querySelector('.market-loading-chart')).not.toBeNull()
    expect(screen.getByRole('status').querySelectorAll('.market-loading-chart-track > g')).toHaveLength(2)
    expect(screen.getByRole('button', { name: 'Analyzing…' }).querySelector('.market-loading-indicator')).not.toBeNull()
    finishRequest(response)
    expect(await screen.findByText('Insufficient evidence')).toBeInTheDocument()
  })

  it('renders an explicit empty result without a zero score', async () => {
    const empty = {
      ...response,
      sentiment: {
        overall_label: 'No eligible news',
        net_score: null,
        mean_probabilities: null,
        counts: { total: 0, positive: 0, negative: 0, neutral: 0, positive_pct: null, negative_pct: null, neutral_pct: null },
      },
      articles: [],
      trend: [],
      warnings: ['No eligible, unique company news articles were found for this period.'],
    }
    vi.mocked(api.analyzeSentiment).mockResolvedValue(empty)
    render(<App />)
    await screen.findByText('Reliance Industries · NSE · RELIANCE.NS')
    fireEvent.click(screen.getByRole('button', { name: 'Analyze sentiment' }))
    expect(await screen.findByText('No relevant news found for the selected stock and date range.')).toBeInTheDocument()
    expect(screen.getByText('No score')).toBeInTheDocument()
  })

  it('switches sentiment charts to detailed tables and back', async () => {
    vi.mocked(api.analyzeSentiment).mockResolvedValue(response)
    render(<App />)
    await screen.findByText('Reliance Industries · NSE · RELIANCE.NS')
    fireEvent.click(screen.getByRole('button', { name: 'Analyze sentiment' }))
    await screen.findByText('Insufficient evidence')

    fireEvent.click(screen.getByRole('button', { name: 'Show distribution table' }))
    expect(screen.getByRole('table', { name: 'Sentiment distribution by classification' })).toBeInTheDocument()
    expect(screen.getByRole('row', { name: /Positive 1 100\.0%/ })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Show distribution chart' }))
    expect(screen.queryByRole('table', { name: 'Sentiment distribution by classification' })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Show trend table' }))
    expect(screen.getByRole('table', { name: 'Article sentiment by publication date' })).toBeInTheDocument()
    expect(screen.getByRole('row', { name: /8 Oct 2026 \+0\.700 1 1 0 0/ })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Show trend chart' }))
    expect(screen.queryByRole('table', { name: 'Article sentiment by publication date' })).not.toBeInTheDocument()
  })
})
