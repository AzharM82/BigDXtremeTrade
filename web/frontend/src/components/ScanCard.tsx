import { useState, useMemo } from 'react'
import { StockResult } from '../types'
import NewsModal from './NewsModal'

interface ScanCardProps {
  title: string
  icon: string
  color: string
  description: string
  stocks: StockResult[]
  loading: boolean
}

const COLOR_MAP: Record<string, { accent: string; glow: string; text: string; gradient: string }> = {
  green:   { accent: '#16a34a', glow: 'glow-green',   text: 'text-green-600',   gradient: 'from-green-500/5 to-transparent' },
  red:     { accent: '#dc2626', glow: 'glow-red',     text: 'text-red-600',     gradient: 'from-red-500/5 to-transparent' },
  emerald: { accent: '#059669', glow: 'glow-emerald', text: 'text-emerald-600', gradient: 'from-emerald-500/5 to-transparent' },
  rose:    { accent: '#e11d48', glow: 'glow-rose',    text: 'text-rose-600',    gradient: 'from-rose-500/5 to-transparent' },
  teal:    { accent: '#0d9488', glow: 'glow-teal',    text: 'text-teal-600',    gradient: 'from-teal-500/5 to-transparent' },
  pink:    { accent: '#db2777', glow: 'glow-pink',    text: 'text-pink-600',    gradient: 'from-pink-500/5 to-transparent' },
  purple:  { accent: '#9333ea', glow: 'glow-purple',  text: 'text-purple-600',  gradient: 'from-purple-500/5 to-transparent' },
  amber:   { accent: '#d97706', glow: 'glow-amber',   text: 'text-amber-600',   gradient: 'from-amber-500/5 to-transparent' },
}

type SortKey = 'ticker' | 'last_price' | 'change_pct_today' | 'change_pct_5d' | 'change_pct_1m' | 'rvol' | 'short_ratio' | 'after_hours_change_pct'
type SortDir = 'asc' | 'desc'

/** Heat-map color: maps % change → light-to-dark green (positive) or red (negative) */
function getHeatColor(val: number, allValues: number[]): string {
  if (val === 0) return '#64748b'

  if (val > 0) {
    const maxUp = Math.max(...allValues.filter(v => v > 0), 0.01)
    const intensity = Math.min(val / maxUp, 1)
    // Light green (55% lightness) → Dark green (22% lightness)
    const lightness = 55 - intensity * 33
    return `hsl(142, 72%, ${lightness}%)`
  } else {
    const maxDown = Math.max(...allValues.filter(v => v < 0).map(Math.abs), 0.01)
    const intensity = Math.min(Math.abs(val) / maxDown, 1)
    const lightness = 55 - intensity * 33
    return `hsl(0, 72%, ${lightness}%)`
  }
}

function ScanCard({ title, icon, color, description, stocks, loading }: ScanCardProps) {
  const colors = COLOR_MAP[color] || COLOR_MAP.green
  const [newsStock, setNewsStock] = useState<StockResult | null>(null)
  const [sortKey, setSortKey] = useState<SortKey>('change_pct_today')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(prev => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  const sortedStocks = useMemo(() => {
    return [...stocks].sort((a, b) => {
      if (sortKey === 'ticker') {
        return sortDir === 'asc'
          ? a.ticker.localeCompare(b.ticker)
          : b.ticker.localeCompare(a.ticker)
      }
      const aNum = (a[sortKey] as number) || 0
      const bNum = (b[sortKey] as number) || 0
      return sortDir === 'asc' ? aNum - bNum : bNum - aNum
    })
  }, [stocks, sortKey, sortDir])

  const todayValues = useMemo(() => stocks.map(s => s.change_pct_today), [stocks])

  const formatChange = (val: number) => {
    const sign = val >= 0 ? '+' : ''
    return `${sign}${val.toFixed(2)}%`
  }

  const SortHeader = ({ label, sortField, className }: { label: string; sortField: SortKey; className?: string }) => (
    <th className={className} onClick={() => toggleSort(sortField)}>
      <span className="sort-header">
        {label}
        <span className={`sort-indicator ${sortKey === sortField ? 'active' : ''}`}>
          {sortKey === sortField ? (sortDir === 'asc' ? '\u25B2' : '\u25BC') : '\u25BC'}
        </span>
      </span>
    </th>
  )

  return (
    <div className={`card ${colors.glow}`}>
      {/* Gradient accent line at top */}
      <div className="h-[2px]" style={{ background: `linear-gradient(90deg, ${colors.accent}, transparent)` }} />

      {/* Card Header */}
      <div className={`card-header bg-gradient-to-r ${colors.gradient}`}>
        <div className="flex items-center gap-3">
          <span className="text-2xl">{icon}</span>
          <div>
            <h2 className="text-base font-bold text-gray-900">{title}</h2>
            <p className="text-[11px] text-gray-400 mt-0.5">{description}</p>
          </div>
        </div>
        <span
          className="count-badge"
          style={{
            background: `${colors.accent}12`,
            color: colors.accent,
            border: `1px solid ${colors.accent}20`,
          }}
        >
          {stocks.length}
        </span>
      </div>

      {/* Content */}
      <div className="card-body">
        {loading ? (
          <div className="p-6 space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="skeleton-pulse h-10 w-full" />
            ))}
          </div>
        ) : stocks.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">{icon}</div>
            <p className="empty-state-title">No stocks found</p>
            <p className="empty-state-subtitle">Run a scan to populate results</p>
          </div>
        ) : (
          <table className="scan-table">
            <thead>
              <tr>
                <SortHeader label="Ticker" sortField="ticker" />
                <SortHeader label="Price" sortField="last_price" />
                <SortHeader label="Today" sortField="change_pct_today" />
                <SortHeader label="5D" sortField="change_pct_5d" />
                <SortHeader label="1M" sortField="change_pct_1m" />
                <SortHeader label="AH%" sortField="after_hours_change_pct" />
                <SortHeader label="RVOL" sortField="rvol" />
                <SortHeader label="Short" sortField="short_ratio" />
                <th>Float</th>
                <th className="text-center">News</th>
              </tr>
            </thead>
            <tbody>
              {sortedStocks.map((stock) => (
                <tr key={stock.ticker}>
                  <td>
                    <div className="font-semibold text-gray-900">{stock.ticker}</div>
                    <div className="text-xs text-gray-400 truncate max-w-[140px]">{stock.company}</div>
                  </td>
                  <td className="font-mono font-semibold text-gray-900">${stock.last_price.toFixed(2)}</td>
                  <td>
                    <span
                      className="font-mono font-bold"
                      style={{ color: getHeatColor(stock.change_pct_today, todayValues) }}
                    >
                      {formatChange(stock.change_pct_today)}
                    </span>
                  </td>
                  <td className={`font-mono font-medium ${stock.change_pct_5d >= 0 ? 'text-positive' : 'text-negative'}`}>
                    {formatChange(stock.change_pct_5d)}
                  </td>
                  <td className={`font-mono font-medium ${stock.change_pct_1m >= 0 ? 'text-positive' : 'text-negative'}`}>
                    {formatChange(stock.change_pct_1m)}
                  </td>
                  <td className={`font-mono font-medium ${stock.after_hours_change_pct >= 0 ? 'text-positive' : 'text-negative'}`}>
                    {formatChange(stock.after_hours_change_pct)}
                  </td>
                  <td className="font-mono">
                    <span
                      className="px-2 py-0.5 rounded font-semibold"
                      style={
                        stock.rvol >= 2
                          ? { background: 'rgba(147, 51, 234, 0.08)', color: '#7c3aed' }
                          : { color: '#94a3b8' }
                      }
                    >
                      {stock.rvol.toFixed(1)}x
                    </span>
                  </td>
                  <td className="font-mono text-gray-500">
                    {stock.short_ratio ? stock.short_ratio.toFixed(1) : '-'}
                  </td>
                  <td className="text-gray-500 text-sm">
                    {stock.float_shares || '-'}
                  </td>
                  <td className="text-center">
                    {stock.news_headline ? (
                      <button
                        onClick={() => setNewsStock(stock)}
                        className="news-icon-btn"
                        title="View news"
                      >
                        {'\uD83D\uDCF0'}
                      </button>
                    ) : (
                      <span className="news-icon-none">--</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* News Modal */}
      <NewsModal stock={newsStock} onClose={() => setNewsStock(null)} />
    </div>
  )
}

export default ScanCard
