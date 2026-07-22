const VARIANTS = {
  primary: { dot: 'bg-primary', glow: 'shadow-[0_0_8px_rgba(78,222,163,0.6)]' },
  error: { dot: 'bg-error', glow: 'shadow-[0_0_8px_rgba(255,180,171,0.6)]' },
  amber: { dot: 'bg-amber-400', glow: 'shadow-[0_0_8px_rgba(251,191,36,0.5)]' },
  neutral: { dot: 'bg-white/20', glow: 'shadow-[0_0_8px_rgba(255,255,255,0.1)]' },
}

export default function StatusDot({ variant = 'primary', pulse = false, size = 'sm', className = '' }) {
  const v = VARIANTS[variant] ?? VARIANTS.primary
  const dimensions = size === 'lg' ? 'w-3 h-3' : 'w-2 h-2'
  return (
    <span
      className={`inline-block rounded-full ${dimensions} ${v.dot} ${v.glow} ${pulse ? 'animate-pulse' : ''} ${className}`}
    />
  )
}
