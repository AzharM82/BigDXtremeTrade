import { useState, useEffect } from 'react'
import ScanCard from './components/ScanCard'
import AdvancedScanCard from './components/AdvancedScanCard'
import SignalBadge from './components/SignalBadge'
import type { ScanResults, AdvancedScanResults, OpportunityResult } from './types'

type TabKey = 'market' | 'strategy' | 'top'

const SCAN_CONFIGS = [
  { key: 'day_up_10',       title: 'Up 10%+ Today',        color: 'green',   icon: '\u{1F4C8}', description: 'Stocks up 10% or more today' },
  { key: 'day_down_10',     title: 'Down 10%+ Today',      color: 'red',     icon: '\u{1F4C9}', description: 'Stocks down 10% or more today' },
  { key: 'week_up_20',      title: 'Up 20%+ This Week',    color: 'emerald', icon: '\u{1F680}', description: 'Stocks up 20% or more in 5 days' },
  { key: 'week_down_20',    title: 'Down 20%+ This Week',  color: 'rose',    icon: '\u{1F4A5}', description: 'Stocks down 20% or more in 5 days' },
  { key: 'month_up_30',     title: 'Up 30%+ This Month',   color: 'teal',    icon: '\u{1F525}', description: 'Stocks up 30% or more in ~21 days' },
  { key: 'month_down_30',   title: 'Down 30%+ This Month', color: 'pink',    icon: '\u{2744}\u{FE0F}', description: 'Stocks down 30% or more in ~21 days' },
  { key: 'high_rvol',       title: 'High Relative Volume',  color: 'purple',  icon: '\u{1F4CA}', description: 'Stocks with 2x+ average volume' },
  { key: 'earnings_movers', title: 'In The News',           color: 'amber',   icon: '\u{1F4F0}', description: 'Stocks with recent news' },
  { key: 'after_hours_up',  title: 'Up After Hours',         color: 'emerald', icon: '\u{1F319}', description: 'Stocks that gapped up 3%+ overnight' },
  { key: 'after_hours_down', title: 'Down After Hours',      color: 'rose',    icon: '\u{1F30C}', description: 'Stocks that gapped down 3%+ overnight' },
]

const ADVANCED_CONFIGS = [
  {
    key: 'earnings_reversal',
    title: 'Earnings Reversal (ERR)',
    color: 'amber',
    icon: '\u{1F4B0}',
    description: 'Beat earnings but gapped down (or missed + gapped up) \u2014 reversal play',
    detailColumns: [
      { key: 'eps_surprise_pct', label: 'EPS Surprise' },
      { key: 'actual_gap_pct', label: 'Gap %' },
      { key: 'expected_move_pct', label: 'Exp Move' },
    ],
  },
  {
    key: 'overextension',
    title: 'Overextension (OMR)',
    color: 'purple',
    icon: '\u{1F4CF}',
    description: 'Stretched 5+ ATRs from 50MA with exhaustion \u2014 mean reversion',
    detailColumns: [
      { key: 'atr_multiple', label: 'ATR Mult' },
      { key: 'rsi', label: 'RSI' },
      { key: 'consecutive_days', label: 'Consec Days' },
    ],
  },
  {
    key: 'event_day',
    title: 'Event Day Volatility',
    color: 'cyan',
    icon: '\u{1F4C5}',
    description: 'FOMC, CPI, NFP creating volatility expansion opportunities',
    detailColumns: [
      { key: 'event_type', label: 'Event' },
      { key: 'days_until', label: 'Days Until' },
      { key: 'range_compression', label: 'Range Compress' },
    ],
  },
  {
    key: 'orb',
    title: 'Opening Range Breakout (ORB)',
    color: 'blue',
    icon: '\u{26A1}',
    description: 'High ADR% stocks breaking out of tight opening ranges on volume',
    detailColumns: [
      { key: 'adr_pct', label: 'ADR%' },
      { key: 'or_high', label: 'OR High' },
      { key: 'or_low', label: 'OR Low' },
      { key: 'volume_ratio', label: 'Vol Ratio' },
    ],
  },
]

const MOMENTUM_CONFIGS = [
  { key: 'day_up_10',    title: 'Day Up 10%+',    color: 'green',   icon: '\u{1F7E2}' },
  { key: 'day_down_10',  title: 'Day Down 10%+',  color: 'red',     icon: '\u{1F534}' },
  { key: 'week_up_20',   title: 'Week Up 20%+',   color: 'emerald', icon: '\u{2B06}\u{FE0F}' },
  { key: 'week_down_20', title: 'Week Down 20%+',  color: 'rose',    icon: '\u{2B07}\u{FE0F}' },
]

function App() {
  const [activeTab, setActiveTab] = useState<TabKey>('market')
  const [data, setData] = useState<ScanResults | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [advancedData, setAdvancedData] = useState<AdvancedScanResults | null>(null)
  const [advancedLoading, setAdvancedLoading] = useState(false)
  const [, setLastRefresh] = useState<Date | null>(null)

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch('/api/scans')
      if (!response.ok) throw new Error('Failed to fetch scan data')
      const result = await response.json()
      setData(result)
      setLastRefresh(new Date())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const fetchAdvancedData = async () => {
    setAdvancedLoading(true)
    try {
      const response = await fetch('/api/advanced/scans')
      if (!response.ok) throw new Error('Failed to fetch advanced scan data')
      const result = await response.json()
      setAdvancedData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setAdvancedLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    fetchAdvancedData()
    const interval = setInterval(() => {
      fetchData()
      fetchAdvancedData()
    }, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [])

  const formatScanTime = (timeStr: string | null) => {
    if (!timeStr) return 'No scan data'
    const date = new Date(timeStr)
    return date.toLocaleString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
      timeZone: 'America/New_York',
    }) + ' ET'
  }

  const getMomentumOpps = (key: string): OpportunityResult[] => {
    if (!advancedData?.momentum) return []
    return (advancedData.momentum as Record<string, OpportunityResult[]>)[key] || []
  }

  const totalBasic = data?.results
    ? Object.values(data.results).reduce((sum, arr) => sum + arr.length, 0)
    : 0

  const tabs: { key: TabKey; label: string; count?: number }[] = [
    { key: 'market',   label: 'Market Scans',      count: totalBasic },
    { key: 'strategy', label: 'Strategy Scanners',  count: advancedData?.total_opportunities || 0 },
    { key: 'top',      label: 'Top Picks',          count: advancedData?.top_opportunities?.length || 0 },
  ]

  return (
    <div className="min-h-screen" style={{ background: '#f1f5f9' }}>
      {/* ── Header ──────────────────────────────────────────────── */}
      <header className="relative" style={{ background: 'linear-gradient(180deg, #ffffff, #f8fafc)', borderBottom: '1px solid rgba(0,0,0,0.06)' }}>
        {/* Top gradient accent line */}
        <div className="h-[3px]" style={{ background: 'linear-gradient(90deg, #2563eb, #7c3aed, #0891b2)' }} />

        <div className="max-w-[1800px] mx-auto px-8 py-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-extrabold text-gray-900 tracking-tight">
              BigDXtreme
              <span className="ml-2 text-lg font-medium text-gray-400">Trade Scanner</span>
            </h1>
            <p className="text-gray-400 text-xs mt-1 tracking-wide uppercase">
              End-of-day opportunity scanner &bull; {data?.total_stocks || 0} stocks in watchlist
            </p>
          </div>
          <div className="flex items-center gap-6">
            <div className="text-right">
              <div className="text-xs text-gray-400 uppercase tracking-wider">Last Scan</div>
              <div className="text-sm text-gray-600 font-medium mt-0.5">
                {data?.scan_time ? formatScanTime(data.scan_time) : 'Never'}
              </div>
            </div>
            <button
              onClick={() => { fetchData(); fetchAdvancedData() }}
              disabled={loading || advancedLoading}
              className="px-5 py-2.5 rounded-lg text-sm font-semibold text-white transition-all duration-200 disabled:opacity-40"
              style={{
                background: loading || advancedLoading ? '#94a3b8' : 'linear-gradient(135deg, #2563eb, #1d4ed8)',
                boxShadow: loading || advancedLoading ? 'none' : '0 4px 14px rgba(37, 99, 235, 0.25)',
              }}
            >
              {loading || advancedLoading ? 'Refreshing...' : 'Refresh Data'}
            </button>
          </div>
        </div>

        {/* ── Tab Navigation ──────────────────────────────────────── */}
        <div className="max-w-[1800px] mx-auto px-8">
          <div className="tab-bar">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`tab-button ${activeTab === tab.key ? 'tab-active' : 'tab-inactive'}`}
              >
                {tab.label}
                {tab.count !== undefined && tab.count > 0 && (
                  <span className="tab-count">{tab.count}</span>
                )}
              </button>
            ))}
          </div>
        </div>
      </header>

      {/* ── Main Content ────────────────────────────────────────── */}
      <main className="max-w-[1800px] mx-auto px-8 py-8">
        {error && (
          <div className="mb-8 p-4 rounded-xl text-red-700 text-sm" style={{ background: 'rgba(220,38,38,0.06)', border: '1px solid rgba(220,38,38,0.12)' }}>
            {error}
          </div>
        )}

        {data?.message && !data.scan_time && activeTab === 'market' && (
          <div className="mb-8 p-4 rounded-xl text-amber-700 text-sm" style={{ background: 'rgba(217,119,6,0.06)', border: '1px solid rgba(217,119,6,0.12)' }}>
            {data.message}
          </div>
        )}

        {/* ── Tab: Market Scans ─────────────────────────────────── */}
        {activeTab === 'market' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {SCAN_CONFIGS.map((config) => (
              <ScanCard
                key={config.key}
                title={config.title}
                icon={config.icon}
                color={config.color}
                description={config.description}
                stocks={data?.results?.[config.key as keyof typeof data.results] || []}
                loading={loading}
              />
            ))}
          </div>
        )}

        {/* ── Tab: Strategy Scanners ────────────────────────────── */}
        {activeTab === 'strategy' && (
          <div className="space-y-8">
            {advancedData?.message && !advancedData.scan_time && (
              <div className="p-4 rounded-xl text-amber-700 text-sm" style={{ background: 'rgba(217,119,6,0.06)', border: '1px solid rgba(217,119,6,0.12)' }}>
                {advancedData.message}
              </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {ADVANCED_CONFIGS.map((config) => (
                <AdvancedScanCard
                  key={config.key}
                  title={config.title}
                  icon={config.icon}
                  color={config.color}
                  description={config.description}
                  opportunities={
                    config.key === 'orb'
                      ? (advancedData?.orb || [])
                      : ((advancedData?.[config.key as keyof AdvancedScanResults] || []) as OpportunityResult[])
                  }
                  loading={advancedLoading}
                  detailColumns={config.detailColumns}
                />
              ))}
            </div>

            {/* Momentum sub-section */}
            <div className="section-header mt-4">
              <h3>Momentum (Trade Plans)</h3>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {MOMENTUM_CONFIGS.map((mc) => (
                <AdvancedScanCard
                  key={mc.key}
                  title={mc.title}
                  icon={mc.icon}
                  color={mc.color}
                  description={`Momentum ${mc.title.toLowerCase()} with full trade plans`}
                  opportunities={getMomentumOpps(mc.key)}
                  loading={advancedLoading}
                  detailColumns={[{ key: 'change_pct', label: '% Change' }]}
                />
              ))}
            </div>
          </div>
        )}

        {/* ── Tab: Top Picks ────────────────────────────────────── */}
        {activeTab === 'top' && (
          <div>
            <div className="flex items-center justify-between mb-8">
              <div>
                <h2 className="text-xl font-bold text-gray-900">Top Opportunities</h2>
                <p className="text-xs text-gray-400 mt-1 uppercase tracking-wider">Ranked by composite score</p>
              </div>
              <div className="text-xs text-gray-400">
                {advancedData?.scan_time ? formatScanTime(advancedData.scan_time) : 'No data'}
              </div>
            </div>

            {advancedLoading ? (
              <div className="space-y-4">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="skeleton-pulse h-16 w-full rounded-xl" />
                ))}
              </div>
            ) : !advancedData?.top_opportunities?.length ? (
              <div className="empty-state">
                <div className="empty-state-icon">{'\u{1F3AF}'}</div>
                <p className="empty-state-title">No top opportunities available</p>
                <p className="empty-state-subtitle">Run an advanced scan to populate results</p>
              </div>
            ) : (
              <div className="space-y-3">
                {advancedData.top_opportunities.map((opp, i) => (
                  <TopPickRow key={opp.ticker} opp={opp} rank={i + 1} />
                ))}
              </div>
            )}
          </div>
        )}
      </main>

      {/* ── Footer ──────────────────────────────────────────────── */}
      <footer className="px-8 py-6 mt-8" style={{ borderTop: '1px solid rgba(0,0,0,0.06)' }}>
        <div className="max-w-[1800px] mx-auto text-center text-gray-400 text-xs tracking-wider uppercase">
          BigDXtreme Trade Scanner &bull; Scans run daily at 4:00 PM ET
        </div>
      </footer>
    </div>
  )
}

function TopPickRow({ opp, rank }: { opp: OpportunityResult; rank: number }) {
  const [expanded, setExpanded] = useState(false)

  const podiumClass = rank === 1 ? 'gold' : rank === 2 ? 'silver' : rank === 3 ? 'bronze' : ''

  return (
    <div className="top-pick-row">
      <div
        className="px-5 py-4 flex items-center gap-5 cursor-pointer transition-colors"
        style={{ background: expanded ? 'rgba(59,130,246,0.02)' : 'transparent' }}
        onClick={() => setExpanded(!expanded)}
      >
        <span className={`top-pick-podium ${podiumClass}`}>{rank}</span>
        <span className="font-bold text-gray-900 text-lg w-20">{opp.ticker}</span>
        <SignalBadge strength={opp.signal_strength} />
        <div className="flex items-center gap-2 w-32">
          <div className="score-bar">
            <div
              className={`score-bar-fill ${opp.score >= 70 ? 'score-high' : opp.score >= 40 ? 'score-mid' : 'score-low'}`}
              style={{ width: `${opp.score}%` }}
            />
          </div>
          <span className="text-sm font-mono font-semibold text-gray-600">{opp.score}</span>
        </div>
        <span
          className="text-xs font-bold uppercase px-2.5 py-1 rounded"
          style={{
            background: opp.direction === 'long' ? 'rgba(22,163,74,0.08)' : 'rgba(220,38,38,0.08)',
            color: opp.direction === 'long' ? '#16a34a' : '#dc2626',
          }}
        >
          {opp.direction}
        </span>
        <span className="text-xs text-gray-400 uppercase font-medium w-24">{opp.opportunity_type_name}</span>
        <span className="text-sm text-gray-500 truncate flex-1" title={opp.headline}>{opp.headline}</span>
        {opp.is_actionable && <span className="actionable-indicator" />}
        <span className={`text-gray-400 text-xs transition-transform duration-200 ${expanded ? 'rotate-90' : ''}`}>{'\u25B6'}</span>
      </div>

      {expanded && opp.tradeplan && (
        <div className="expand-panel">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h4 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3">Trade Plan</h4>
              <div className="rounded-xl overflow-hidden" style={{ background: '#f8fafc', border: '1px solid rgba(0,0,0,0.06)' }}>
                <div className="grid grid-cols-2 gap-x-6 gap-y-3 p-4 text-sm">
                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-gray-400 mb-0.5">Entry</div>
                    <div className="font-mono font-semibold text-gray-900">${opp.tradeplan.entry_price.toFixed(2)}</div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-gray-400 mb-0.5">Stop</div>
                    <div className="font-mono font-semibold text-red-600">${opp.tradeplan.stop_loss.toFixed(2)}</div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-gray-400 mb-0.5">Target 1</div>
                    <div className="font-mono font-semibold text-green-600">${opp.tradeplan.target_1.toFixed(2)}</div>
                  </div>
                  {opp.tradeplan.target_2 != null && (
                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-gray-400 mb-0.5">Target 2</div>
                      <div className="font-mono font-semibold text-green-600">${opp.tradeplan.target_2.toFixed(2)}</div>
                    </div>
                  )}
                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-gray-400 mb-0.5">R:R</div>
                    <div className={`font-mono font-bold ${opp.tradeplan.risk_reward_t1 >= 2 ? 'text-green-600' : 'text-amber-600'}`}>
                      {opp.tradeplan.risk_reward_t1.toFixed(1)} : 1
                    </div>
                  </div>
                </div>
              </div>
            </div>
            {Object.keys(opp.details).length > 0 && (
              <div>
                <h4 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3">Details</h4>
                <div className="grid grid-cols-2 gap-x-6 gap-y-2">
                  {Object.entries(opp.details).map(([k, v]) => (
                    <div key={k}>
                      <div className="text-[10px] text-gray-400 uppercase tracking-wider">{k.replace(/_/g, ' ')}</div>
                      <div className="text-sm text-gray-700 font-mono">
                        {v === null || v === undefined ? '-' : typeof v === 'number' ? (v as number).toFixed(2) : String(v)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default App
