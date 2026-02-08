import { SignalStrength } from '../types'

interface SignalBadgeProps {
  strength: SignalStrength
}

const SIGNAL_STYLES: Record<SignalStrength, { bg: string; text: string; border: string }> = {
  WEAK:     { bg: 'rgba(100, 116, 139, 0.08)', text: '#64748b', border: 'rgba(100, 116, 139, 0.15)' },
  MODERATE: { bg: 'rgba(59, 130, 246, 0.08)',   text: '#2563eb', border: 'rgba(59, 130, 246, 0.15)' },
  STRONG:   { bg: 'rgba(22, 163, 74, 0.08)',    text: '#16a34a', border: 'rgba(22, 163, 74, 0.15)' },
  EXTREME:  { bg: 'rgba(220, 38, 38, 0.08)',    text: '#dc2626', border: 'rgba(220, 38, 38, 0.15)' },
}

function SignalBadge({ strength }: SignalBadgeProps) {
  const style = SIGNAL_STYLES[strength] || SIGNAL_STYLES.WEAK

  return (
    <span
      className="signal-badge"
      style={{
        background: style.bg,
        color: style.text,
        border: `1px solid ${style.border}`,
      }}
    >
      {strength}
    </span>
  )
}

export default SignalBadge
