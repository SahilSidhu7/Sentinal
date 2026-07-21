const COLORS = {
  critical: 'bg-red-500/15 text-red-400 border-red-500/30',
  high: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
  medium: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  low: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
}

export default function SeverityBadge({ severity }) {
  const cls = COLORS[severity] ?? 'bg-gray-500/15 text-gray-400 border-gray-500/30'
  return (
    <span className={`inline-block rounded border px-2 py-0.5 text-xs font-medium capitalize ${cls}`}>
      {severity}
    </span>
  )
}
