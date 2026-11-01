import type { AnalyzeResult, Stock } from './types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, init)
  } catch {
    throw new Error('Cannot reach the sentiment API. Check that the FastAPI backend is running.')
  }
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = payload.detail
    const message = typeof detail === 'string'
      ? detail
      : detail?.message
        || (Array.isArray(detail) ? detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join('; ') : '')
    throw new Error(message || `Request failed (${response.status})`)
  }
  return payload as T
}

export function getStocks(): Promise<Stock[]> {
  return apiRequest('/api/v1/stocks')
}

export function getSources(): Promise<{
  providers: { name: string; configured: boolean; availability: string }[]
  model: string
  model_status: 'not_loaded' | 'loading' | 'loaded' | 'error' | 'unknown'
  demo_mode_available: boolean
  max_age_days: number
}> {
  return apiRequest('/api/v1/sentiment/sources')
}

export type AnalyzeInput = {
  symbol: string
  exchange: 'NSE' | 'BSE'
  start_date: string
  end_date: string
  max_articles: number
  demo_mode: boolean
}

export function analyzeSentiment(input: AnalyzeInput): Promise<AnalyzeResult> {
  return apiRequest('/api/v1/sentiment/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}
