import { Tradeplan } from '../types'

interface TradePlanBadgeProps {
  plan: Tradeplan
}

function TradePlanBadge({ plan }: TradePlanBadgeProps) {
  const isLong = plan.direction === 'long'
  const dirColor = isLong ? '#16a34a' : '#dc2626'
  const dirBg = isLong ? 'rgba(22, 163, 74, 0.06)' : 'rgba(220, 38, 38, 0.06)'
  const dirBorder = isLong ? 'rgba(22, 163, 74, 0.12)' : 'rgba(220, 38, 38, 0.12)'

  return (
    <div className="rounded-xl overflow-hidden" style={{ background: '#f8fafc', border: '1px solid rgba(0,0,0,0.06)' }}>
      {/* Direction banner */}
      <div
        className="px-4 py-2 flex items-center justify-between text-xs font-bold uppercase tracking-wider"
        style={{ background: dirBg, borderBottom: `1px solid ${dirBorder}` }}
      >
        <span style={{ color: dirColor }}>{plan.direction}</span>
        <span className={`font-mono ${plan.risk_reward_t1 >= 2 ? 'text-green-600' : 'text-amber-600'}`}>
          {plan.risk_reward_t1.toFixed(1)} : 1 R/R
        </span>
      </div>

      {/* Levels grid */}
      <div className="grid grid-cols-2 gap-x-6 gap-y-3 p-4 text-sm">
        <div>
          <div className="text-[10px] uppercase tracking-wider text-gray-400 mb-0.5">Entry</div>
          <div className="font-mono font-semibold text-gray-900">${plan.entry_price.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wider text-gray-400 mb-0.5">Stop Loss</div>
          <div className="font-mono font-semibold text-red-600">${plan.stop_loss.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wider text-gray-400 mb-0.5">Target 1</div>
          <div className="font-mono font-semibold text-green-600">${plan.target_1.toFixed(2)}</div>
        </div>
        {plan.target_2 != null && (
          <div>
            <div className="text-[10px] uppercase tracking-wider text-gray-400 mb-0.5">Target 2</div>
            <div className="font-mono font-semibold text-green-600">${plan.target_2.toFixed(2)}</div>
          </div>
        )}
        {plan.target_3 != null && (
          <div>
            <div className="text-[10px] uppercase tracking-wider text-gray-400 mb-0.5">Target 3</div>
            <div className="font-mono font-semibold text-green-600">${plan.target_3.toFixed(2)}</div>
          </div>
        )}
        {plan.position_size_shares > 0 && (
          <div>
            <div className="text-[10px] uppercase tracking-wider text-gray-400 mb-0.5">Position</div>
            <div className="font-mono text-gray-900">{plan.position_size_shares} shares</div>
          </div>
        )}
        {plan.max_risk_dollars > 0 && (
          <div>
            <div className="text-[10px] uppercase tracking-wider text-gray-400 mb-0.5">Max Risk</div>
            <div className="font-mono text-red-600">${plan.max_risk_dollars.toFixed(0)}</div>
          </div>
        )}
      </div>
    </div>
  )
}

export default TradePlanBadge
