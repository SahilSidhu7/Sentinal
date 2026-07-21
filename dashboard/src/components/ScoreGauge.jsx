import { LineChart, Line, ResponsiveContainer, YAxis, Tooltip } from 'recharts'

function scoreColor(score) {
  if (score >= 80) return '#4ade80'
  if (score >= 60) return '#facc15'
  return '#f87171'
}

export default function ScoreGauge({ score, history }) {
  const color = scoreColor(score)
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-4">
      <div className="flex items-baseline gap-2">
        <span className="text-4xl font-semibold" style={{ color }}>
          {score}
        </span>
        <span className="text-sm text-gray-500">/ 100 security score</span>
      </div>
      <div className="mt-3 h-20">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={history}>
            <YAxis domain={[0, 100]} hide />
            <Tooltip
              contentStyle={{ background: '#111827', border: '1px solid #1f2937', fontSize: 12 }}
              labelStyle={{ color: '#9ca3af' }}
            />
            <Line type="monotone" dataKey="score" stroke={color} strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
