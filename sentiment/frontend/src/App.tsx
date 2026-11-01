import { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from 'react'
import {
  Activity, AlertTriangle, ArrowDownRight, ArrowUpRight, BarChart3, CalendarDays,
  CheckCircle2, ChevronDown, CircleHelp, Clock3, ExternalLink, FileText,
  Newspaper, Search, ShieldAlert, Sparkles, TrendingUp,
} from 'lucide-react'
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { analyzeSentiment, getSources, getStocks, type AnalyzeInput } from './api'
import StockLogo from './StockLogo'
import type { AnalyzeResult, Evidence, Stock } from './types'

const COLORS = { Positive: '#168a63', Negative: '#d94f68', Neutral: '#64748b' }
const today = new Date()
const dateString = (date: Date) => date.toISOString().slice(0, 10)
const initialEnd = dateString(today)
const startForDays = (days: number) => {
  const start = new Date(today)
  start.setDate(today.getDate() - days + 1)
  return dateString(start)
}
const initialStart = startForDays(30)
const dateRangeOptions = [
  { value: '7', label: 'Last 7 Days', detail: 'A focused view of recent coverage' },
  { value: '30', label: 'Last 30 Days', detail: 'Default news analysis window' },
  { value: 'custom', label: 'Custom date range', detail: 'Choose exact start and end dates' },
] as const
const articleLimitOptions = [
  { value: '10', label: '10 articles', detail: 'Quick market snapshot' },
  { value: '20', label: '20 articles', detail: 'Compact coverage' },
  { value: '30', label: '30 articles', detail: 'Balanced research view' },
  { value: '50', label: '50 articles', detail: 'Expanded coverage' },
  { value: '100', label: '100 articles', detail: 'Maximum available coverage' },
] as const

function formatDate(value: string, withTime = false) {
  const date = new Date(value)
  return new Intl.DateTimeFormat('en-IN', withTime
    ? { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }
    : { dateStyle: 'medium', timeZone: 'UTC' }).format(date)
}

function percent(value: number | null) {
  return value === null ? '—' : `${value.toFixed(1)}%`
}

function scoreLabel(value: number | null) {
  if (value === null) return 'No score'
  return `${value > 0 ? '+' : ''}${value.toFixed(3)}`
}

function App() {
  const [stocks, setStocks] = useState<Stock[]>([])
  const [stockValue, setStockValue] = useState('RELIANCE.NS')
  const [stockMenuOpen, setStockMenuOpen] = useState(false)
  const [activeStockIndex, setActiveStockIndex] = useState(0)
  const [startDate, setStartDate] = useState(initialStart)
  const [endDate, setEndDate] = useState(initialEnd)
  const [dateRange, setDateRange] = useState<'7' | '30' | 'custom'>('30')
  const [dateRangeMenuOpen, setDateRangeMenuOpen] = useState(false)
  const [activeDateRangeIndex, setActiveDateRangeIndex] = useState(1)
  const dateRangeTriggerRef = useRef<HTMLButtonElement>(null)
  const dateRangeOptionRefs = useRef<Array<HTMLButtonElement | null>>([])
  const [maxArticles, setMaxArticles] = useState('30')
  const [articleLimitMenuOpen, setArticleLimitMenuOpen] = useState(false)
  const [activeArticleLimitIndex, setActiveArticleLimitIndex] = useState(2)
  const articleLimitTriggerRef = useRef<HTMLButtonElement>(null)
  const articleLimitOptionRefs = useRef<Array<HTMLButtonElement | null>>([])
  const [demoMode, setDemoMode] = useState(false)
  const [result, setResult] = useState<AnalyzeResult | null>(null)
  const [sources, setSources] = useState<Awaited<ReturnType<typeof getSources>> | null>(null)
  const [loading, setLoading] = useState(false)
  const [modelLoading, setModelLoading] = useState(false)
  const [error, setError] = useState('')
  const activeProvider = sources?.providers[0]?.name ?? 'NewsAPI'
  const providerKey = activeProvider === 'GNews' ? 'GNEWS_API_KEY' : 'NEWS_API_KEY'
  const providerSignupUrl = activeProvider === 'GNews'
    ? 'https://gnews.io/register'
    : 'https://newsapi.org/register'
  const providerWebsite = activeProvider === 'GNews' ? 'gnews.io' : 'newsapi.org'
  const minNewsDate = sources?.max_age_days
    ? dateString(new Date(today.getTime() - (sources.max_age_days - 1) * 24 * 60 * 60 * 1000))
    : undefined
  const selectedDateRange = dateRangeOptions.find((option) => option.value === dateRange)!

  useEffect(() => {
    getStocks().then((items) => setStocks(items)).catch((reason: Error) => setError(reason.message))
    getSources().then(setSources).catch((reason: Error) => setError(reason.message))
  }, [])

  useEffect(() => {
    if (dateRangeMenuOpen) {
      dateRangeOptionRefs.current[activeDateRangeIndex]?.focus()
    }
  }, [activeDateRangeIndex, dateRangeMenuOpen])

  useEffect(() => {
    if (articleLimitMenuOpen) {
      articleLimitOptionRefs.current[activeArticleLimitIndex]?.focus()
    }
  }, [activeArticleLimitIndex, articleLimitMenuOpen])

  const selectedStock = useMemo(() => stocks.find((stock) =>
    stock.symbol.toLowerCase() === stockValue.toLowerCase()
    || stock.company_name.toLowerCase() === stockValue.toLowerCase()
    || stock.aliases.some((alias) => alias.toLowerCase() === stockValue.toLowerCase()),
  ), [stocks, stockValue])
  const stockOptions = useMemo(() => {
    const query = stockValue.trim().toLowerCase()
    if (!query) return stocks.slice(0, 10)
    return stocks
      .filter((stock) => [stock.symbol, stock.company_name, ...stock.aliases]
        .some((value) => value.toLowerCase().includes(query)))
      .sort((left, right) => {
        const leftExact = left.symbol.toLowerCase() === query || left.company_name.toLowerCase() === query
        const rightExact = right.symbol.toLowerCase() === query || right.company_name.toLowerCase() === query
        if (leftExact !== rightExact) return leftExact ? -1 : 1
        return left.company_name.localeCompare(right.company_name)
      })
      .slice(0, 10)
  }, [stocks, stockValue])

  function chooseStock(stock: Stock) {
    setStockValue(stock.symbol)
    setStockMenuOpen(false)
    setActiveStockIndex(0)
  }

  function handleStockKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape') {
      setStockMenuOpen(false)
      return
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      setStockMenuOpen(true)
      if (stockOptions.length) {
        setActiveStockIndex((index) => event.key === 'ArrowDown'
          ? (index + 1) % stockOptions.length
          : (index - 1 + stockOptions.length) % stockOptions.length)
      }
      return
    }
    if (event.key === 'Enter' && stockMenuOpen && stockOptions.length) {
      event.preventDefault()
      chooseStock(stockOptions[activeStockIndex] ?? stockOptions[0])
    }
  }

  async function runAnalysis() {
    setError('')
    setResult(null)
    if (!selectedStock) {
      setError('Choose a supported company from the stock selector.')
      return
    }
    if (!startDate || !endDate) {
      setError('Choose both a start date and an end date.')
      return
    }
    if (startDate > initialEnd) {
      setError('Start date cannot be in the future.')
      return
    }
    if (endDate > initialEnd) {
      setError('End date cannot be in the future.')
      return
    }
    if (endDate < startDate) {
      setError('End date must be on or after start date.')
      return
    }
    if (!demoMode && minNewsDate && startDate < minNewsDate) {
      setError(`The configured provider supports only the most recent ${sources?.max_age_days} days. Choose a newer start date.`)
      return
    }
    setLoading(true)
    setModelLoading(!demoMode)
    const request: AnalyzeInput = {
      symbol: selectedStock.symbol,
      exchange: selectedStock.exchange,
      start_date: startDate,
      end_date: endDate,
      max_articles: Number(maxArticles),
      demo_mode: demoMode,
    }
    try {
      const response = await analyzeSentiment(request)
      setResult(response)
      setSources(await getSources())
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : 'Sentiment analysis failed.'
      setError(message)
      try {
        setSources(await getSources())
      } catch (statusError) {
        if (statusError instanceof Error) setError(`${message} Unable to refresh model status: ${statusError.message}`)
      }
    } finally {
      setLoading(false)
      setModelLoading(false)
    }
  }

  function changeDateRange(value: '7' | '30' | 'custom') {
    setDateRange(value)
    if (value !== 'custom') {
      setStartDate(startForDays(Number(value)))
      setEndDate(initialEnd)
    }
  }

  function openDateRangeMenu() {
    setActiveDateRangeIndex(dateRangeOptions.findIndex((option) => option.value === dateRange))
    setDateRangeMenuOpen(true)
  }

  function handleDateRangeKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === 'Escape') {
      setDateRangeMenuOpen(false)
      dateRangeTriggerRef.current?.focus()
      return
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveDateRangeIndex((index) => (index + (event.key === 'ArrowDown' ? 1 : -1) + dateRangeOptions.length) % dateRangeOptions.length)
    }
    if (event.key === 'Home') {
      event.preventDefault()
      setActiveDateRangeIndex(0)
    }
    if (event.key === 'End') {
      event.preventDefault()
      setActiveDateRangeIndex(dateRangeOptions.length - 1)
    }
  }

  function openArticleLimitMenu() {
    setActiveArticleLimitIndex(articleLimitOptions.findIndex((option) => option.value === maxArticles))
    setArticleLimitMenuOpen(true)
  }

  function handleArticleLimitKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === 'Escape') {
      setArticleLimitMenuOpen(false)
      articleLimitTriggerRef.current?.focus()
      return
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveArticleLimitIndex((index) => (index + (event.key === 'ArrowDown' ? 1 : -1) + articleLimitOptions.length) % articleLimitOptions.length)
    }
    if (event.key === 'Home') {
      event.preventDefault()
      setActiveArticleLimitIndex(0)
    }
    if (event.key === 'End') {
      event.preventDefault()
      setActiveArticleLimitIndex(articleLimitOptions.length - 1)
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await runAnalysis()
  }

  return (
    <div className="market-theme min-h-screen bg-[#090f1b] text-slate-100">
      <aside className="market-sidebar">
        <div className="market-side-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          <a className="market-nav-link active" href="#sentiment"><Newspaper size={16} />News Sentiment</a>
        </nav>
        <div className="market-side-bottom">
          <div className="market-side-label">RESEARCH TOOLS</div>
          <a className="market-docs-link" href="http://127.0.0.1:8001/docs" target="_blank" rel="noreferrer"><FileText size={14} />API documentation <ExternalLink size={11} /></a>
          <div className="market-side-status"><span className={demoMode ? 'market-status-dot demo' : 'market-status-dot'} />{demoMode ? 'LOCAL DEMO MODE' : `${activeProvider.toUpperCase()} ${sources?.providers[0]?.configured ? 'CONNECTED' : 'NOT CONFIGURED'}`}</div>
          <div className="market-side-status"><span className={sources?.model_status === 'loaded' ? 'market-status-dot demo' : 'market-status-dot'} />FINBERT {modelLoading ? 'LOADING' : (sources?.model_status ?? 'UNKNOWN').replace('_', ' ').toUpperCase()}</div>
          <p>Sentiment research is not a price forecast or investment advice.</p>
        </div>
      </aside>
      <div className="market-main">
        <header className="market-topbar">
          <div><span>Stock News Sentiment Analysis</span><b>/</b>Financial News</div>
          <div className="flex items-center gap-3">
            <span className="market-topbar-badge"><span /> FINANCIAL NEWS</span>
          </div>
        </header>

      <main id="sentiment" className="mx-auto max-w-[1440px] px-5 pb-16 pt-8 lg:px-10">
        <section className="sentiment-page-header mb-7">
          <div>
            <div className="mb-2 flex items-center gap-2 text-[10px] font-semibold tracking-[.24em] text-blue-600"><span className="h-px w-6 bg-blue-500" /> FINANCIAL NEWS INTELLIGENCE <span className="h-px w-6 bg-blue-500" /></div>
            <h1 className="sentiment-page-title font-semibold tracking-tight text-blue-950">Stock News Sentimental Analysis</h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-400">Financial news sentiment for the selected company, based on retrieved articles and explainable model outputs.</p>
          </div>
          <img className="sentiment-page-logo" src="/stockq-market-logo.png" alt="Stock News Sentiment Analysis" />
        </section>

        <form onSubmit={submit} className="analysis-controls mb-5 rounded-2xl border border-white/[0.08] bg-[#101a29] p-4 shadow-xl shadow-black/10 sm:p-5">
          <div className="analysis-controls-heading">
            <div className="analysis-controls-title">
              <span className="analysis-controls-icon"><Activity size={17} /></span>
              <span>
                <span className="analysis-controls-eyebrow">RESEARCH WORKSPACE</span>
                <span className="analysis-controls-name">Configure news scan</span>
              </span>
            </div>
            <span className="analysis-controls-status"><span />{demoMode ? 'DEMO DATA' : sources?.providers[0]?.configured ? `${activeProvider.toUpperCase()} READY` : 'PROVIDER SETUP REQUIRED'}</span>
          </div>
          <div className="analysis-range-row">
            <div className="analysis-range-field date-range-picker">
              <span className="analysis-field-label">DATE RANGE</span>
              <button
                ref={dateRangeTriggerRef}
                type="button"
                aria-label="Date range"
                aria-haspopup="listbox"
                aria-expanded={dateRangeMenuOpen}
                aria-controls="date-range-options"
                className="date-range-trigger"
                onClick={() => dateRangeMenuOpen ? setDateRangeMenuOpen(false) : openDateRangeMenu()}
                onKeyDown={(event) => {
                  if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    openDateRangeMenu()
                  }
                }}
              >
                <CalendarDays size={16} />
                <span>{selectedDateRange.label}</span>
                <ChevronDown size={16} className={dateRangeMenuOpen ? 'date-range-chevron open' : 'date-range-chevron'} />
              </button>
              {dateRangeMenuOpen && <div id="date-range-options" className="date-range-menu" role="listbox" aria-label="Date range options">
                {dateRangeOptions.map((option, index) => (
                  <button
                    key={option.value}
                    ref={(element) => { dateRangeOptionRefs.current[index] = element }}
                    type="button"
                    role="option"
                    aria-selected={dateRange === option.value}
                    tabIndex={activeDateRangeIndex === index ? 0 : -1}
                    className={`date-range-option${activeDateRangeIndex === index ? ' active' : ''}`}
                    onMouseEnter={() => setActiveDateRangeIndex(index)}
                    onKeyDown={handleDateRangeKeyDown}
                    onClick={() => {
                      changeDateRange(option.value)
                      setDateRangeMenuOpen(false)
                      dateRangeTriggerRef.current?.focus()
                    }}
                  >
                    <span className="date-range-option-copy"><span>{option.label}</span><small>{option.detail}</small></span>
                    {dateRange === option.value && <CheckCircle2 size={17} className="date-range-selected-icon" />}
                  </button>
                ))}
              </div>}
            </div>
            <span className="analysis-range-note">
              {dateRange === 'custom' ? 'CUSTOM WINDOW' : dateRange === '7' ? 'RECENT MARKET COVERAGE' : 'DEFAULT LOOKBACK WINDOW'}
            </span>
          </div>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-[1.5fr_.78fr_.78fr_.75fr_.75fr_auto] xl:items-end">
            <label className={`stock-picker-field block${stockMenuOpen ? ' is-open' : ''}`}>
              <span className="analysis-field-label">COMPANY OR TICKER</span>
              <span className="relative block">
                <Search size={16} className="analysis-control-icon" />
                <input
                  aria-label="Company or ticker"
                  aria-autocomplete="list"
                  aria-expanded={stockMenuOpen}
                  aria-controls="stock-options"
                  aria-activedescendant={stockMenuOpen && stockOptions[activeStockIndex] ? `stock-option-${stockOptions[activeStockIndex].symbol}` : undefined}
                  role="combobox"
                  value={stockValue}
                  onFocus={() => setStockMenuOpen(true)}
                  onBlur={() => setStockMenuOpen(false)}
                  onKeyDown={handleStockKeyDown}
                  onChange={(event) => {
                    setStockValue(event.target.value)
                    setActiveStockIndex(0)
                    setStockMenuOpen(true)
                  }}
                  placeholder="Search by company or ticker"
                  className="h-11 w-full rounded-lg border border-white/10 bg-[#0b1320] pl-10 pr-3 text-sm text-slate-100 outline-none placeholder:text-slate-600 focus:border-emerald-400/60"
                />
                {stockMenuOpen && <div id="stock-options" className="stock-option-list" role="listbox" aria-label="Available stocks">
                  {stockOptions.length ? stockOptions.map((stock, index) => (
                    <button
                      id={`stock-option-${stock.symbol}`}
                      key={stock.symbol}
                      type="button"
                      role="option"
                      aria-selected={selectedStock?.symbol === stock.symbol}
                      className={`stock-option${index === activeStockIndex ? ' active' : ''}`}
                      onMouseEnter={() => setActiveStockIndex(index)}
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => chooseStock(stock)}
                    >
                      <StockLogo stock={stock} className="stock-option-logo" />
                      <span className="stock-option-symbol">{stock.symbol}</span>
                      <span className="stock-option-name">{stock.company_name}</span>
                      <span className="stock-option-exchange">{stock.exchange}</span>
                    </button>
                  )) : <div className="stock-option-empty">No matching stocks</div>}
                </div>}
              </span>
            </label>
            <label className="block">
              <span className="analysis-field-label">START DATE</span>
              <span className="analysis-control-wrap"><CalendarDays size={15} className="analysis-control-icon" /><input aria-label="Start date" type="date" min={demoMode ? undefined : minNewsDate} max={endDate || initialEnd} value={startDate} onChange={(event) => { setStartDate(event.target.value); setDateRange('custom') }} className="analysis-date-input h-11 w-full rounded-lg border border-white/10 bg-[#0b1320] pl-10 pr-2 text-sm text-slate-200 outline-none focus:border-emerald-400/60" /></span>
            </label>
            <label className="block">
              <span className="analysis-field-label">END DATE</span>
              <span className="analysis-control-wrap"><CalendarDays size={15} className="analysis-control-icon" /><input aria-label="End date" type="date" min={startDate} max={initialEnd} value={endDate} onChange={(event) => { setEndDate(event.target.value); setDateRange('custom') }} className="analysis-date-input h-11 w-full rounded-lg border border-white/10 bg-[#0b1320] pl-10 pr-2 text-sm text-slate-200 outline-none focus:border-emerald-400/60" /></span>
            </label>
            <div className="block">
              <span className="analysis-field-label">MAX ARTICLES</span>
              <div className="max-articles-picker">
                <button
                  ref={articleLimitTriggerRef}
                  type="button"
                  aria-label="Maximum articles"
                  aria-haspopup="listbox"
                  aria-expanded={articleLimitMenuOpen}
                  aria-controls="article-limit-options"
                  className="date-range-trigger"
                  onClick={() => articleLimitMenuOpen ? setArticleLimitMenuOpen(false) : openArticleLimitMenu()}
                  onKeyDown={(event) => {
                    if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault()
                      openArticleLimitMenu()
                    }
                  }}
                >
                  <FileText size={16} />
                  <span>{articleLimitOptions.find((option) => option.value === maxArticles)?.label}</span>
                  <ChevronDown size={16} className={articleLimitMenuOpen ? 'date-range-chevron open' : 'date-range-chevron'} />
                </button>
                {articleLimitMenuOpen && <div id="article-limit-options" className="date-range-menu" role="listbox" aria-label="Maximum article options">
                  {articleLimitOptions.map((option, index) => (
                    <button
                      key={option.value}
                      ref={(element) => { articleLimitOptionRefs.current[index] = element }}
                      type="button"
                      role="option"
                      aria-selected={maxArticles === option.value}
                      tabIndex={activeArticleLimitIndex === index ? 0 : -1}
                      className={`date-range-option${activeArticleLimitIndex === index ? ' active' : ''}`}
                      onMouseEnter={() => setActiveArticleLimitIndex(index)}
                      onKeyDown={handleArticleLimitKeyDown}
                      onClick={() => {
                        setMaxArticles(option.value)
                        setArticleLimitMenuOpen(false)
                        articleLimitTriggerRef.current?.focus()
                      }}
                    >
                      <span className="date-range-option-copy"><span>{option.label}</span><small>{option.detail}</small></span>
                      {maxArticles === option.value && <CheckCircle2 size={17} className="date-range-selected-icon" />}
                    </button>
                  ))}
                </div>}
              </div>
            </div>
            {sources?.demo_mode_available && <label className="flex h-11 items-center gap-2 self-end rounded-lg border border-amber-300/15 bg-amber-400/[0.045] px-3 text-xs text-amber-200/90" title="Development-only synthetic data; never combined with real provider articles.">
              <input aria-label="Use demo fixtures" type="checkbox" checked={demoMode} onChange={(event) => setDemoMode(event.target.checked)} className="accent-amber-400" />
              Demo fixtures (dev only)
            </label>}
            <button type="submit" disabled={loading} className="flex h-11 items-center justify-center gap-2 rounded-lg bg-blue-600 px-5 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60">
              {loading ? <span className="market-loading-indicator" aria-hidden="true"><span /><span /><span /><svg viewBox="0 0 32 24"><path d="m2 18 7-7 5 4 9-10 7 3" /></svg></span> : <Activity size={17} />}
              {loading ? 'Analyzing…' : 'Analyze sentiment'}
            </button>
          </div>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[10px] text-slate-500">
            <span className="selected-stock-summary">{selectedStock && <StockLogo stock={selectedStock} />}{selectedStock ? `${selectedStock.company_name} · ${selectedStock.exchange} · ${selectedStock.symbol}` : 'Select a configured company to continue.'}</span>
            <span>{demoMode ? 'Synthetic fixtures and heuristic classifier; not real news or FinBERT output.' : 'Live analysis uses the configured news provider and ProsusAI/finbert.'}</span>
          </div>
          {!demoMode && !sources?.providers[0]?.configured && <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] leading-5 text-amber-900">
            To enable real news, obtain an API key at <a className="font-semibold underline" href={providerSignupUrl} target="_blank" rel="noreferrer">{providerWebsite}</a> and set <code>{providerKey}</code> in <code>sentiment\backend\.env</code>, then restart the backend. Never put the key in frontend configuration.
          </p>}
        </form>

        {error && <div role="alert" className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-rose-400/20 bg-rose-400/[0.07] p-4 text-sm text-rose-200"><span className="flex items-start gap-3"><AlertTriangle size={18} className="mt-0.5 shrink-0" /><span>{error}</span></span><button type="button" onClick={() => void runAnalysis()} disabled={loading} className="rounded-md border border-rose-300/40 px-3 py-1.5 text-xs font-semibold hover:bg-rose-50 disabled:opacity-50">Retry</button></div>}
        {loading && <div role="status" className="market-loading-status mb-5 rounded-xl border border-emerald-300/15 bg-emerald-300/[0.035] p-5 text-sm text-slate-300">
          <div className="market-loading-status-label">
            <Activity size={17} aria-hidden="true" />
            <span>{modelLoading ? 'Retrieving provider news and, if eligible articles are found, running ProsusAI/finbert…' : 'Retrieving and deduplicating news, then analyzing eligible articles…'}</span>
          </div>
          <svg className="market-loading-chart" viewBox="0 0 1000 48" preserveAspectRatio="none" aria-hidden="true">
            <defs>
              <linearGradient id="market-loading-sentiment-gradient" x1="0" y1=".5" x2="1" y2=".5" gradientUnits="objectBoundingBox">
                <stop offset="0%" stopColor="#168a63" />
                <stop offset="10%" stopColor="#168a63" />
                <stop offset="10%" stopColor="#d94f68" />
                <stop offset="20%" stopColor="#d94f68" />
                <stop offset="20%" stopColor="#168a63" />
                <stop offset="30%" stopColor="#168a63" />
                <stop offset="30%" stopColor="#d94f68" />
                <stop offset="40%" stopColor="#d94f68" />
                <stop offset="40%" stopColor="#168a63" />
                <stop offset="50%" stopColor="#168a63" />
                <stop offset="50%" stopColor="#d94f68" />
                <stop offset="60%" stopColor="#d94f68" />
                <stop offset="60%" stopColor="#168a63" />
                <stop offset="70%" stopColor="#168a63" />
                <stop offset="70%" stopColor="#d94f68" />
                <stop offset="80%" stopColor="#d94f68" />
                <stop offset="80%" stopColor="#168a63" />
                <stop offset="90%" stopColor="#168a63" />
                <stop offset="90%" stopColor="#d94f68" />
                <stop offset="100%" stopColor="#d94f68" />
              </linearGradient>
              <path id="market-loading-ecg-beat" d="M0 24H16L20 21L24 27L30 24H39L44 22L48 26L55 4L62 43L69 17L75 24H100" />
            </defs>
            <path className="market-loading-chart-grid" d="M0 12H1000M0 24H1000M0 36H1000" />
            <path className="market-loading-chart-volume" d="M18 45V36M52 45V28M86 45V33M120 45V18M154 45V30M188 45V24M222 45V35M256 45V20M290 45V27M324 45V14M358 45V30M392 45V22M426 45V34M460 45V17M494 45V28M528 45V20M562 45V32M596 45V13M630 45V26M664 45V18M698 45V34M732 45V22M766 45V29M800 45V16M834 45V31M868 45V19M902 45V27M936 45V14M970 45V25" />
            <g className="market-loading-chart-track">
              {[0, 1000].map((offset) => (
                <g key={offset} transform={`translate(${offset})`}>
                  <g className="market-loading-chart-price">
                    {Array.from({ length: 10 }, (_, index) => <use key={index} href="#market-loading-ecg-beat" x={index * 100} />)}
                  </g>
                </g>
              ))}
            </g>
          </svg>
        </div>}

        {!result && !loading && !error && (
          <div className="mb-6 rounded-2xl border border-dashed border-white/10 bg-[#101a29]/50 p-8 text-center">
            <div className="mx-auto mb-3 grid size-11 place-items-center rounded-xl bg-emerald-400/10 text-emerald-300"><Sparkles size={20} /></div>
            <h2 className="font-medium text-slate-200">Ready to analyze financial news</h2>
            <p className="mx-auto mt-2 max-w-lg text-xs leading-5 text-slate-500">Choose a company and date range to retrieve financial news and analyze eligible headlines/descriptions with ProsusAI/finbert. The first live analysis downloads the model; missing provider credentials or model errors are reported without synthetic fallback.</p>
          </div>
        )}

        {result && <Dashboard result={result} modelStatus={sources?.model_status ?? 'unknown'} />}
      </main>
        </div>
    </div>
  )
}

function Dashboard({ result, modelStatus }: { result: AnalyzeResult; modelStatus: string }) {
  const [showDistributionTable, setShowDistributionTable] = useState(false)
  const [showTrendTable, setShowTrendTable] = useState(false)
  const { sentiment, source } = result
  const counts = sentiment.counts
  const sentimentColor = sentiment.overall_label === 'Positive' ? 'text-emerald-300' : sentiment.overall_label === 'Negative' ? 'text-rose-300' : 'text-slate-200'
  const distribution = [
    { name: 'Positive', value: counts.positive, pct: counts.positive_pct ?? 0, fill: COLORS.Positive },
    { name: 'Negative', value: counts.negative, pct: counts.negative_pct ?? 0, fill: COLORS.Negative },
    { name: 'Neutral', value: counts.neutral, pct: counts.neutral_pct ?? 0, fill: COLORS.Neutral },
  ].filter((item) => item.value > 0)
  const trend = fillTrendGaps(result.trend)

  return (
    <div className="sentiment-results space-y-5">
      {source.mode === 'demo' && <div role="status" className="flex items-center gap-2 rounded-xl border border-amber-300/20 bg-amber-300/[0.07] px-4 py-3 text-xs font-medium text-amber-200"><AlertTriangle size={15} /> DEMO MODE — synthetic local fixtures and heuristic classifications, not actual news or FinBERT.</div>}
      {result.warnings.map((warning) => <div key={warning} className="flex items-start gap-2 rounded-xl border border-amber-300/15 bg-amber-300/[0.045] px-4 py-3 text-xs leading-5 text-amber-100/80"><ShieldAlert size={15} className="mt-0.5 shrink-0 text-amber-300" />{warning}</div>)}
      <section className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/[0.07] bg-[#101a29] px-4 py-3 text-[11px] text-slate-400">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2"><span className="selected-stock-summary font-semibold text-slate-200"><StockLogo stock={result.stock} />{result.stock.company_name}</span><span>{result.stock.exchange} · {result.stock.symbol}</span><span>{formatDate(result.period.start)} — {formatDate(result.period.end)}</span></div>
        <div className="flex items-center gap-2"><Clock3 size={13} className="text-emerald-300" />{source.provider} · {source.cache_status === 'hit' ? 'cached provider results' : 'provider results retrieved'} {formatDate(source.retrieved_at, true)} UTC</div>
      </section>
      <section className="flex flex-wrap gap-x-6 gap-y-2 rounded-xl border border-white/[0.07] bg-[#101a29] px-4 py-3 text-[10px] text-slate-500">
        <span>Latest publication: <strong className="text-slate-700">{result.articles.length ? formatDate(result.articles.reduce((latest, article) => article.published_at > latest ? article.published_at : latest, result.articles[0].published_at), true) : 'None'}</strong></span>
        <span>Analysis timestamp: <strong className="text-slate-700">{formatDate(source.analyzed_at, true)} UTC</strong></span>
        {source.mode === 'demo'
          ? <span>Demo classifier: <strong className="text-slate-700">{source.model_id}</strong> · not FinBERT</span>
          : <span>FinBERT: <strong className="text-slate-700">{source.model_id}</strong> · {modelStatus}</span>}
        {source.inference_cache_status === 'hit' && <span>Cached model inference</span>}
      </section>

      <section aria-label="Article inclusion" className="rounded-xl border border-white/[0.07] bg-[#101a29] p-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2">
            <div className="text-[9px] font-semibold tracking-[.12em] text-slate-500">FETCHED FROM PROVIDER</div>
            <div className="mt-1 text-lg font-semibold text-slate-100">{source.articles_retrieved}</div>
          </div>
          <div className="rounded-lg border border-emerald-300/10 bg-emerald-300/[0.035] px-3 py-2">
            <div className="text-[9px] font-semibold tracking-[.12em] text-emerald-300/70">ELIGIBLE & ANALYZED</div>
            <div className="mt-1 text-lg font-semibold text-emerald-200">{source.articles_eligible}</div>
          </div>
          <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2">
            <div className="text-[9px] font-semibold tracking-[.12em] text-slate-500">FETCHED, NOT ANALYZED</div>
            <div className="mt-1 text-lg font-semibold text-slate-300">{Math.max(0, source.articles_retrieved - source.articles_eligible)}</div>
          </div>
        </div>
        <p className="mt-3 text-[10px] leading-4 text-slate-500">
          Only eligible articles shown in the News feed affect the sentiment score. The fetched-but-not-analyzed count may include irrelevant results, duplicates, incomplete records, or results beyond the selected article limit; the current API does not separate those reasons. Fetched count covers provider pages requested, not every matching article available.
        </p>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <MetricCard label="OVERALL SENTIMENT" value={sentiment.overall_label} detail="FinBERT scores · project thresholds ±0.10" icon={<Activity size={16} />} valueClass={sentimentColor} tone={sentiment.overall_label === 'Positive' ? 'positive' : sentiment.overall_label === 'Negative' ? 'negative' : 'neutral'} />
        <MetricCard label="NET SENTIMENT SCORE" value={scoreLabel(sentiment.net_score)} detail="Mean positive − negative probability" icon={<TrendingUp size={16} />} valueClass={sentiment.net_score === null ? '' : sentiment.net_score > 0.1 ? 'text-emerald-300' : sentiment.net_score < -0.1 ? 'text-rose-300' : ''} tone={sentiment.net_score === null || Math.abs(sentiment.net_score) <= 0.1 ? 'neutral' : sentiment.net_score > 0 ? 'positive' : 'negative'} />
        <MetricCard label="ARTICLES ANALYZED" value={String(counts.total)} detail={`${source.articles_retrieved} retrieved · ${source.articles_eligible} eligible`} icon={<FileText size={16} />} tone="blue" />
        <MetricCard label="POSITIVE ARTICLES" value={percent(counts.positive_pct)} detail={`${counts.positive} positive`} icon={<ArrowUpRight size={16} />} valueClass="text-emerald-300" tone="positive" />
        <MetricCard label="NEGATIVE / NEUTRAL" value={`${percent(counts.negative_pct)} / ${percent(counts.neutral_pct)}`} detail={`${counts.negative} negative · ${counts.neutral} neutral`} icon={<ArrowDownRight size={16} />} valueClass="text-rose-200" tone="negative" />
      </section>

      {counts.total === 0 ? (
        <section className="rounded-2xl border border-dashed border-white/10 bg-[#101a29]/60 px-6 py-12 text-center">
          <Newspaper size={24} className="mx-auto text-slate-500" />
          <h2 className="mt-3 font-medium text-slate-200">No relevant news found for the selected stock and date range.</h2>
          <p className="mt-2 text-xs text-slate-500">{source.articles_retrieved ? `${source.articles_retrieved} provider article(s) were retrieved, but none passed the company relevance and duplicate filters. ` : 'The provider returned no articles. '}No sentiment score has been calculated. Try widening the recent search period or reviewing company aliases.</p>
        </section>
      ) : <>
        <section className="grid gap-5 xl:grid-cols-[.8fr_1.2fr]">
          <Panel title="Sentiment distribution" eyebrow="ARTICLE CLASSIFICATION" icon={<button type="button" className="chart-view-toggle" aria-label={showDistributionTable ? 'Show distribution chart' : 'Show distribution table'} aria-pressed={showDistributionTable} onClick={() => setShowDistributionTable((visible) => !visible)}>{showDistributionTable ? <BarChart3 size={17} /> : <FileText size={17} />}</button>}>
            {showDistributionTable ? (
              <div className="sentiment-table-wrap">
                <table className="sentiment-data-table">
                  <caption>Sentiment distribution by classification</caption>
                  <thead><tr><th scope="col">Sentiment</th><th scope="col">Articles</th><th scope="col">Share</th></tr></thead>
                  <tbody>{[
                    ['Positive', counts.positive, counts.positive_pct],
                    ['Negative', counts.negative, counts.negative_pct],
                    ['Neutral', counts.neutral, counts.neutral_pct],
                  ].map(([label, amount, pct]) => <tr key={String(label)}><th scope="row"><span className="sentiment-table-dot" style={{ background: COLORS[label as keyof typeof COLORS] }} />{label}</th><td>{amount}</td><td>{percent(pct as number | null)}</td></tr>)}</tbody>
                  <tfoot><tr><th scope="row">Total</th><td>{counts.total}</td><td>{counts.total ? '100.0%' : '—'}</td></tr></tfoot>
                </table>
              </div>
            ) : <div className="grid items-center gap-2 sm:grid-cols-[.9fr_1.1fr]">
              <div className="relative h-52 min-w-0">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart><Pie data={distribution} dataKey="value" nameKey="name" innerRadius={58} outerRadius={82} paddingAngle={3} stroke="none">{distribution.map((entry) => <Cell key={entry.name} fill={entry.fill} />)}</Pie><Tooltip content={<DistributionTooltip />} /></PieChart>
                </ResponsiveContainer>
                <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center"><strong className="text-2xl text-slate-100">{counts.total}</strong><span className="text-[10px] text-slate-500">articles</span></div>
              </div>
              <div className="space-y-3">{[
                ['Positive', counts.positive, counts.positive_pct],
                ['Negative', counts.negative, counts.negative_pct],
                ['Neutral', counts.neutral, counts.neutral_pct],
              ].map(([label, amount, pct]) => <div key={String(label)} className="flex items-center justify-between gap-3 text-xs"><span className="flex items-center gap-2 text-slate-300"><span className="size-2 rounded-full" style={{ background: COLORS[label as keyof typeof COLORS] }} />{label}</span><span className="font-mono text-slate-500">{amount} · {percent(pct as number | null)}</span></div>)}</div>
            </div>}
            <p className="mt-1 text-[10px] leading-4 text-slate-500">Percentages use all eligible unique articles; they are not price-movement probabilities.</p>
          </Panel>

          <Panel title="Sentiment trend" eyebrow="BY PUBLICATION DATE" icon={<button type="button" className="chart-view-toggle" aria-label={showTrendTable ? 'Show trend chart' : 'Show trend table'} aria-pressed={showTrendTable} onClick={() => setShowTrendTable((visible) => !visible)}>{showTrendTable ? <Activity size={17} /> : <TrendingUp size={17} />}</button>}>
            {showTrendTable ? (
              <div className="sentiment-table-wrap sentiment-trend-table">
                <table className="sentiment-data-table">
                  <caption>Article sentiment by publication date</caption>
                  <thead><tr><th scope="col">Publication date</th><th scope="col">Mean score</th><th scope="col">Articles</th><th scope="col">Positive</th><th scope="col">Negative</th><th scope="col">Neutral</th></tr></thead>
                  <tbody>{trend.map((point) => <tr key={point.date}><th scope="row">{formatDate(point.date)}</th><td>{point.mean_score === null ? '—' : scoreLabel(point.mean_score)}</td><td>{point.article_count ?? '—'}</td><td>{point.article_count === null ? '—' : point.positive}</td><td>{point.article_count === null ? '—' : point.negative}</td><td>{point.article_count === null ? '—' : point.neutral}</td></tr>)}</tbody>
                </table>
              </div>
            ) : trend.length ? <div className="h-60 min-w-0">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trend} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
                  <CartesianGrid stroke="#ffffff0d" vertical={false} />
                  <XAxis dataKey="short_date" tick={{ fill: '#526176', fontSize: 12 }} axisLine={false} tickLine={false} />
                  <YAxis yAxisId="score" domain={[-1, 1]} tick={{ fill: '#526176', fontSize: 12 }} axisLine={false} tickLine={false} />
                  <YAxis yAxisId="count" orientation="right" allowDecimals={false} tick={{ fill: '#526176', fontSize: 12 }} axisLine={false} tickLine={false} />
                  <Tooltip content={<TrendTooltip />} />
                  <Legend wrapperStyle={{ fontSize: 12, color: '#526176' }} />
                  <Line yAxisId="score" type="monotone" dataKey="mean_score" name="Mean article score" stroke="#397d5c" strokeWidth={2.5} dot={{ r: 3, fill: '#397d5c' }} connectNulls={false} />
                  <Line yAxisId="count" type="monotone" dataKey="article_count" name="Article count" stroke="#ad8b50" strokeWidth={2} strokeDasharray="4 4" dot={{ r: 2, fill: '#ad8b50' }} connectNulls={false} />
                </LineChart>
              </ResponsiveContainer>
            </div> : <EmptyPanel message="No dated articles to plot." />}
            <p className="mt-1 text-[10px] leading-4 text-slate-500">Score scale −1 to +1; only dates with eligible articles are shown. Count uses the right axis.</p>
          </Panel>
        </section>

        <section className="grid gap-5 xl:grid-cols-[1.35fr_.65fr]">
          <Panel title="News feed" eyebrow={`${counts.total} ELIGIBLE ARTICLES`} icon={<Newspaper size={15} />}>
            <div className="space-y-3">
              {result.articles.map((article) => <ArticleCard key={`${article.url}-${article.headline}`} article={article} />)}
            </div>
          </Panel>
          <Panel title="Evidence summary" eyebrow="DETERMINISTIC · CITED" icon={<Sparkles size={15} />}>
            <p className="mb-4 text-xs leading-5 text-slate-300">{result.summary.overview}</p>
            <EvidenceGroup title="Positive coverage" items={result.summary.positive_themes} color="text-emerald-300" />
            <EvidenceGroup title="Negative coverage" items={result.summary.negative_themes} color="text-rose-300" />
            <EvidenceGroup title="Neutral or conflicting" items={result.summary.neutral_or_conflicting} color="text-slate-300" />
            <div className="mt-5 rounded-lg border border-white/[0.07] bg-black/10 p-3">
              <h3 className="mb-2 flex items-center gap-2 text-[10px] font-semibold tracking-wider text-slate-300"><CircleHelp size={13} /> LIMITATIONS</h3>
              <ul className="space-y-2 text-[10px] leading-4 text-slate-500">{result.summary.limitations.map((item) => <li key={item}>• {item}</li>)}</ul>
            </div>
          </Panel>
        </section>
      </>}

      <Panel title="Analysis methodology" eyebrow="INTERPRETATION GUIDE" icon={<ShieldAlert size={15} />}>
        <div className="grid gap-4 text-[11px] leading-5 text-slate-400 md:grid-cols-3">
          <p><strong className="text-slate-200">Article score</strong><br />Positive-class probability minus negative-class probability, from −1 to +1. Article probabilities are the model's classification outputs, not calibrated market forecasts.</p>
          <p><strong className="text-slate-200">Overall label</strong><br />Equal-weight arithmetic mean of eligible article scores. Greater than +0.10 is Positive; below −0.10 is Negative; values between are Neutral or mixed. Fewer than 3 articles is insufficient evidence.</p>
          <p><strong className="text-slate-200">Data controls</strong><br />Company aliases filter relevance. Articles are deduplicated by canonical URL and normalized headline. Missing descriptions use headline-only inference and are flagged.</p>
        </div>
      </Panel>
      <div className="flex flex-wrap justify-between gap-2 px-1 text-[10px] text-slate-600"><span>Provider: {source.provider} · Model: {source.model_id}</span><span>FinBERT is not specifically trained for Indian equity news. Educational research only; not financial advice.</span></div>
    </div>
  )
}

type TrendChartPoint = {
  date: string
  article_count: number | null
  mean_score: number | null
  positive: number
  negative: number
  neutral: number
  short_date: string
}

function fillTrendGaps(points: AnalyzeResult['trend']): TrendChartPoint[] {
  if (points.length < 2) {
    return points.map((item) => ({
      ...item,
      short_date: new Date(`${item.date}T00:00:00Z`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', timeZone: 'UTC' }),
    }))
  }
  const byDate = new Map(points.map((point) => [point.date, point]))
  const start = new Date(`${points[0].date}T00:00:00Z`)
  const end = new Date(`${points.at(-1)!.date}T00:00:00Z`)
  const filled: Omit<TrendChartPoint, 'short_date'>[] = []
  for (const cursor = new Date(start); cursor <= end; cursor.setUTCDate(cursor.getUTCDate() + 1)) {
    const key = cursor.toISOString().slice(0, 10)
    filled.push(byDate.get(key) ?? {
      date: key,
      article_count: null,
      mean_score: null,
      positive: 0,
      negative: 0,
      neutral: 0,
    })
  }
  return filled.map((item) => ({
    ...item,
    short_date: new Date(`${item.date}T00:00:00Z`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', timeZone: 'UTC' }),
  }))
}

function MetricCard({ label, value, detail, icon, valueClass = '', tone }: { label: string; value: string; detail: string; icon: ReactNode; valueClass?: string; tone: 'positive' | 'negative' | 'neutral' | 'blue' }) {
  return <article className="sentiment-metric-card rounded-xl border border-white/[0.07] bg-[#101a29] p-4" data-tone={tone}><div className="flex items-center justify-between text-[9px] font-semibold tracking-[.14em] text-slate-500"><span>{label}</span><span className="text-slate-600">{icon}</span></div><div className={`mt-4 truncate text-xl font-semibold tracking-tight ${valueClass || 'text-slate-100'}`} title={value}>{value}</div><div className="mt-1 text-[10px] text-slate-500">{detail}</div></article>
}

function Panel({ title, eyebrow, icon, children }: { title: string; eyebrow: string; icon: ReactNode; children: ReactNode }) {
  return <section className="sentiment-panel min-w-0 rounded-2xl border border-white/[0.07] bg-[#101a29] p-4 shadow-lg shadow-black/[0.08] sm:p-5"><div className="mb-4 flex items-start justify-between gap-3"><div><div className="text-[9px] font-semibold tracking-[.18em] text-emerald-300/65">{eyebrow}</div><h2 className="mt-1.5 text-base font-semibold text-slate-100">{title}</h2></div><span className="rounded-lg border border-white/[0.07] p-2 text-slate-500">{icon}</span></div>{children}</section>
}

function ArticleCard({ article }: { article: AnalyzeResult['articles'][number] }) {
  const style = article.sentiment === 'Positive' ? 'border-emerald-300/15 bg-emerald-300/[0.07] text-emerald-200' : article.sentiment === 'Negative' ? 'border-rose-300/15 bg-rose-300/[0.07] text-rose-200' : 'border-white/10 bg-white/[0.04] text-slate-300'
  const probabilities = [
    ['Positive', article.probabilities.positive, COLORS.Positive],
    ['Negative', article.probabilities.negative, COLORS.Negative],
    ['Neutral', article.probabilities.neutral, COLORS.Neutral],
  ] as const
  return <article className="sentiment-article rounded-xl border border-white/[0.07] bg-[#0b1320]/65 p-4">
    <div className="mb-2 flex flex-wrap items-center justify-between gap-2"><span className="flex items-center gap-1.5 text-[10px] text-slate-500"><Newspaper size={12} />{article.publisher}<span className="px-1 text-slate-700">·</span><time dateTime={article.published_at}>{formatDate(article.published_at, true)} UTC</time></span><span className="flex flex-wrap items-center gap-2"><span className="rounded-full border border-emerald-300/15 bg-emerald-300/[0.06] px-2 py-1 text-[9px] font-semibold text-emerald-200">Included in sentiment</span><span className={`rounded-full border px-2.5 py-1 text-[9px] font-semibold ${style}`}>{article.sentiment} · {scoreLabel(article.article_score)}</span></span></div>
    <h3 className="text-sm font-medium leading-5 text-slate-100"><a className="hover:text-emerald-200" href={article.url} target="_blank" rel="noopener noreferrer">{article.headline}<ExternalLink size={12} className="ml-1 inline text-slate-600" /></a></h3>
    {article.description && <p className="mt-2 text-xs leading-5 text-slate-400">{article.description}</p>}
    {article.analyzed_headline_only && <p className="mt-2 text-[10px] text-amber-300/80">Headline-only model input; source provided no description.</p>}
    <div className="mt-3 flex flex-wrap gap-2">{probabilities.map(([label, value, color]) => <span key={label} className="rounded-md border border-white/[0.06] px-2 py-1 text-[9px] text-slate-500"><span style={{ color }}>{label}</span> {value.toFixed(3)}</span>)}</div>
    <div className="mt-2 text-[9px] text-slate-600">Source: {article.source_provider} · Search mapping: {article.search_query}</div>
    <div className="mt-2 text-[9px] text-slate-600">Model: {article.model_id} · analyzed {formatDate(article.analyzed_at, true)} UTC</div>
  </article>
}

function EvidenceGroup({ title, items, color }: { title: string; items: Evidence[]; color: string }) {
  return <div className="mb-4"><h3 className={`mb-2 text-[10px] font-semibold ${color}`}>{title}</h3>{items.length ? <ul className="space-y-2">{items.map((item) => <li key={item.url} className="border-l border-white/10 pl-3 text-[10px] leading-4 text-slate-400"><a href={item.url} target="_blank" rel="noopener noreferrer" className="hover:text-emerald-200">{item.headline} <ExternalLink size={10} className="inline" /></a><span className="mt-1 block text-slate-600">{item.text}</span></li>)}</ul> : <p className="text-[10px] text-slate-600">No articles in this group.</p>}</div>
}

function EmptyPanel({ message }: { message: string }) {
  return <div className="grid h-52 place-items-center text-xs text-slate-500">{message}</div>
}

function DistributionTooltip({ active, payload }: { active?: boolean; payload?: { payload: { name: string; value: number; pct: number } }[] }) {
  if (!active || !payload?.length) return null
  const item = payload[0].payload
  return <div className="rounded-lg border border-white/10 bg-[#080d16] px-3 py-2 text-xs text-slate-200 shadow-xl">{item.name}: {item.value} articles · {item.pct.toFixed(1)}%</div>
}

function TrendTooltip({ active, payload, label }: { active?: boolean; payload?: { payload: { article_count: number; mean_score: number; positive: number; negative: number; neutral: number } }[]; label?: string }) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload
  return <div className="rounded-lg border border-white/10 bg-[#080d16] px-3 py-2 text-[10px] leading-5 text-slate-200 shadow-xl"><div className="mb-1 font-semibold">{label}</div><div>Mean score: {point.mean_score.toFixed(3)} · {point.article_count} articles</div><div>Positive {point.positive} · Negative {point.negative} · Neutral {point.neutral}</div></div>
}

export default App
