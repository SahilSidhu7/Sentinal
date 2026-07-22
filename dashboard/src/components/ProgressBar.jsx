export default function ProgressBar({ pct, barClassName = 'bg-primary', trackClassName = 'bg-white/5', height = 'h-1.5' }) {
  return (
    <div className={`w-full ${trackClassName} ${height} rounded-full overflow-hidden`}>
      <div
        className={`${barClassName} h-full transition-all duration-1000`}
        style={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
      />
    </div>
  )
}
