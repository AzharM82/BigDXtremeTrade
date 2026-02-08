export interface StockResult {
  ticker: string
  company: string
  sector: string
  industry: string
  last_price: number
  change_pct_today: number
  change_pct_5d: number
  change_pct_1m: number
  atr: number
  rvol: number
  after_hours_change_pct: number
  news_headline: string
  news_link: string
  news_items: { headline: string; link: string }[]
  scan_type: string
  short_ratio: number
  float_shares: string
  short_float_pct: number
}

export interface PriceLevel {
  price: number
  label: string
  level_type: string
}

export interface Tradeplan {
  entry_price: number
  stop_loss: number
  target_1: number
  target_2: number | null
  target_3: number | null
  direction: string
  position_size_shares: number
  option_contract: string | null
  max_risk_dollars: number
  risk_per_share: number
  reward_t1: number
  risk_reward_t1: number
}

export type SignalStrength = 'WEAK' | 'MODERATE' | 'STRONG' | 'EXTREME'

export interface OpportunityResult {
  ticker: string
  opportunity_type: string
  opportunity_type_name: string
  direction: string
  signal_strength: SignalStrength
  signal_strength_value: number
  detected_at: string
  headline: string
  details: Record<string, unknown>
  tradeplan: Tradeplan | null
  key_levels: PriceLevel[]
  score: number
  is_actionable: boolean
}

export interface AdvancedScanResults {
  earnings_reversal: OpportunityResult[]
  overextension: OpportunityResult[]
  event_day: OpportunityResult[]
  orb: OpportunityResult[]
  momentum: {
    day_up_10?: OpportunityResult[]
    day_down_10?: OpportunityResult[]
    week_up_20?: OpportunityResult[]
    week_down_20?: OpportunityResult[]
  }
  top_opportunities: OpportunityResult[]
  scan_time: string | null
  total_opportunities: number
  message?: string
}

export interface ScanResults {
  scan_time: string | null
  total_stocks: number
  results: {
    day_up_10: StockResult[]
    day_down_10: StockResult[]
    week_up_20: StockResult[]
    week_down_20: StockResult[]
    month_up_30: StockResult[]
    month_down_30: StockResult[]
    high_rvol: StockResult[]
    earnings_movers: StockResult[]
    after_hours_up: StockResult[]
    after_hours_down: StockResult[]
  }
  message?: string
}
