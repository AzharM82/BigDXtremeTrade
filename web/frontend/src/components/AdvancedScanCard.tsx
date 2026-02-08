import { Fragment, useState, useMemo } from 'react'
import { OpportunityResult } from '../types'
import SignalBadge from './SignalBadge'
import TradePlanBadge from './TradePlanBadge'

interface AdvancedScanCardProps {
  title: string
  icon: string
  color: string
  description: string
  opportunities: OpportunityResult[]
  loading: boolean
  detailColumns?: { key: string; label: string }[]
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
  blue:    { accent: '#2563eb', glow: 'glow-blue',    text: 'text-blue-600',    gradient: 'from-blue-500/5 to-transparent' },
  cyan:    { accent: '#0891b2', glow: 'glow-cyan',    text: 'text-cyan-600',    gradient: 'from-cyan-500/5 to-transparent' },
}

type SortKey = 'ticker' | 'score' | 'direction' | 'signal'
type SortDir = 'asc' | 'desc'

const SIGNAL_ORDER: Record<string, number> = { WEAK: 1, MODERATE: 2, STRONG: 3, EXTREME: 4 }

function formatDetailValue(val: unknown): string {
  if (val === null || val === undefined) return '-'
  if (typeof val === 'number') return val.toFixed(2)
  return String(val)
}

function AdvancedScanCard({ title, icon, color, description, opportunities, loading, detailColumns }: AdvancedScanCardProps) {
  const colors = COLOR_MAP[color] || COLOR_MAP.green
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null)
  const [sortKey, setSortKey] = useState<SortKey>('score')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const toggleExpand = (ticker: string) => {
    setExpandedTicker(expandedTicker === ticker ? null : ticker)
  }

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(prev => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  const sortedOpps = useMemo(() => {
    return [...opportunities].sort((a, b) => {
      let cmp = 0
      switch (sortKey) {
        case 'ticker':
          cmp = a.ticker.localeCompare(b.ticker)
          break
        case 'score':
          cmp = a.score - b.score
          break
        case 'direction':
          cmp = a.direction.localeCompare(b.direction)
          break
        case 'signal':
          cmp = (SIGNAL_ORDER[a.signal_strength] || 0) - (SIGNAL_ORDER[b.signal_strength] || 0)
          break
      }
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [opportunities, sortKey, sortDir])

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
      {/* Gradient accent line */}
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
          {opportunities.length}
        </span>
      </div>

      {/* Content */}
      <div className="card-body">
        {loading ? (
          <div className="p-6 space-y-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="skeleton-pulse h-12 w-full" />
            ))}
          </div>
        ) : opportunities.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">{icon}</div>
            <p className="empty-state-title">No opportunities found</p>
            <p className="empty-state-subtitle">Run an advanced scan to populate results</p>
          </div>
        ) : (
          <table className="scan-table">
            <thead>
              <tr>
                <th className="w-8"></th>
                <SortHeader label="Ticker" sortField="ticker" />
                <SortHeader label="Signal" sortField="signal" />
                <SortHeader label="Score" sortField="score" />
                <SortHeader label="Direction" sortField="direction" />
                <th>Headline</th>
                {detailColumns?.map((col) => (
                  <th key={col.key}>{col.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sortedOpps.map((opp) => (
                <Fragment key={opp.ticker}>
                  <tr
                    className="cursor-pointer"
                    onClick={() => toggleExpand(opp.ticker)}
                  >
                    <td className="text-gray-400 w-8">
                      <span className={`inline-block transition-transform duration-200 ${expandedTicker === opp.ticker ? 'rotate-90' : ''}`}>
                        {'\u25B6'}
                      </span>
                    </td>
                    <td>
                      <div className="font-bold text-gray-900">{opp.ticker}</div>
                    </td>
                    <td>
                      <SignalBadge strength={opp.signal_strength} />
                    </td>
                    <td>
                      <div className="flex items-center gap-2">
                        <div className="score-bar">
                          <div
                            className={`score-bar-fill ${opp.score >= 70 ? 'score-high' : opp.score >= 40 ? 'score-mid' : 'score-low'}`}
                            style={{ width: `${opp.score}%` }}
                          />
                        </div>
                        <span className="font-mono font-semibold text-gray-600">{opp.score}</span>
                      </div>
                    </td>
                    <td>
                      <span
                        className="font-bold uppercase px-2.5 py-0.5 rounded"
                        style={{
                          background: opp.direction === 'long' ? 'rgba(22,163,74,0.08)' : 'rgba(220,38,38,0.08)',
                          color: opp.direction === 'long' ? '#16a34a' : '#dc2626',
                        }}
                      >
                        {opp.direction}
                      </span>
                    </td>
                    <td>
                      <span className="text-gray-500 truncate block max-w-[240px]" title={opp.headline}>
                        {opp.headline}
                      </span>
                    </td>
                    {detailColumns?.map((col) => (
                      <td key={col.key} className="font-mono text-gray-500">
                        {formatDetailValue(opp.details[col.key])}
                      </td>
                    ))}
                  </tr>
                  {expandedTicker === opp.ticker && (
                    <tr className="expanded-row">
                      <td colSpan={6 + (detailColumns?.length || 0)} className="p-0">
                        <div className="expand-panel">
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            {/* Trade Plan */}
                            {opp.tradeplan && (
                              <div>
                                <h4 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3">Trade Plan</h4>
                                <TradePlanBadge plan={opp.tradeplan} />
                              </div>
                            )}

                            {/* Key Levels */}
                            {opp.key_levels.length > 0 && (
                              <div>
                                <h4 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3">Key Levels</h4>
                                <div className="space-y-2">
                                  {opp.key_levels.map((kl, i) => (
                                    <div key={i} className="flex items-center gap-2.5">
                                      <span className={`w-2 h-2 rounded-full ${kl.level_type === 'support' ? 'bg-green-500' : kl.level_type === 'resistance' ? 'bg-red-500' : 'bg-blue-500'}`} />
                                      <span className="text-gray-400 text-sm">{kl.label}</span>
                                      <span className="text-gray-900 font-mono font-medium">${kl.price.toFixed(2)}</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* Details */}
                            {Object.keys(opp.details).length > 0 && (
                              <div className="md:col-span-2">
                                <h4 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3">Scanner Details</h4>
                                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-x-6 gap-y-2">
                                  {Object.entries(opp.details).map(([k, v]) => (
                                    <div key={k}>
                                      <div className="text-[10px] text-gray-400 uppercase tracking-wider">{k.replace(/_/g, ' ')}</div>
                                      <div className="text-gray-700 font-mono">{formatDetailValue(v)}</div>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>

                          {/* Actionable indicator */}
                          {opp.is_actionable && (
                            <div className="mt-5 pt-4 flex items-center gap-2.5" style={{ borderTop: '1px solid rgba(0,0,0,0.06)' }}>
                              <span className="actionable-indicator" />
                              <span className="text-green-600 font-bold uppercase tracking-wider">Actionable Trade</span>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

export default AdvancedScanCard
