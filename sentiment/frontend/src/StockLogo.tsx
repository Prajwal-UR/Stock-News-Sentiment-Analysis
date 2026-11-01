import { useEffect, useState } from 'react'
import type { Stock } from './types'

type StockLogoProps = {
  stock: Stock
  className?: string
}

export default function StockLogo({ stock, className = '' }: StockLogoProps) {
  const [imageFailed, setImageFailed] = useState(false)
  const token = import.meta.env.VITE_LOGO_DEV_PUBLISHABLE_KEY?.trim()
  const initials = stock.company_name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word.replace(/[^a-z0-9]/gi, '')[0] ?? '')
    .join('')
    .toUpperCase()
  const colorIndex = [...stock.symbol].reduce(
    (hash, character) => (hash * 31 + character.charCodeAt(0)) >>> 0,
    0,
  ) % 6
  const logoUrl = token
    ? `https://img.logo.dev/ticker/${encodeURIComponent(stock.symbol)}?${new URLSearchParams({
      token,
      size: '64',
      format: 'png',
    })}`
    : null
  const colors = [
    ['#e8f4ee', '#286e50'],
    ['#eaf0fb', '#365b9a'],
    ['#fff2e4', '#a85b1b'],
    ['#f2ebfa', '#70439b'],
    ['#e8f3f5', '#287080'],
    ['#faecec', '#a44152'],
  ] as const
  const [background, foreground] = colors[colorIndex]
  const classes = `stock-logo${className ? ` ${className}` : ''}`

  useEffect(() => {
    setImageFailed(false)
  }, [stock.symbol])

  return (
    <span className={classes} aria-hidden="true" style={{ backgroundColor: background, color: foreground }}>
      {logoUrl && !imageFailed
        ? <img src={logoUrl} alt="" onError={() => setImageFailed(true)} />
        : <svg viewBox="0 0 40 40" focusable="false">
          <path d="M20 3.5 36.5 13v14L20 36.5 3.5 27V13L20 3.5Z" fill="none" stroke="currentColor" strokeOpacity=".22" />
          <text x="20" y="22" textAnchor="middle" dominantBaseline="middle">{initials}</text>
        </svg>}
    </span>
  )
}
