const LABELS = {
  high: 'HIGH RISK',
  medium: 'MEDIUM',
  safe: 'SAFE',
}

export default function SeverityBadge({ severity }) {
  return (
    <span className="font-label-caps text-[10px] text-on-tertiary-fixed-variant px-2 py-1 border border-white/10 rounded">
      {LABELS[severity] ?? severity.toUpperCase()}
    </span>
  )
}
