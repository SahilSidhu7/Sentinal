import { useEffect, useState } from 'react'
import { getScore, getFindings, connectLiveFeed } from '../lib/api'
import ScoreGauge from '../components/ScoreGauge'
import LiveFeed from '../components/LiveFeed'
import SeverityBadge from '../components/SeverityBadge'

export default function Overview() {
  const [score, setScore] = useState({ score: 0, history: [] })
  const [findings, setFindings] = useState([])
  const [liveEvents, setLiveEvents] = useState([])

  useEffect(() => {
    getScore().then(setScore)
    getFindings().then(setFindings)
    const disconnect = connectLiveFeed((event) => setLiveEvents((prev) => [event, ...prev]))
    return disconnect
  }, [])

  const openFindings = findings.filter((f) => f.status === 'open')

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <ScoreGauge score={score.score} history={score.history} />
        <LiveFeed events={liveEvents} />
      </div>

      <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-4">
        <h2 className="mb-2 text-sm font-medium text-gray-400">
          Open findings ({openFindings.length})
        </h2>
        {openFindings.length === 0 ? (
          <p className="text-sm text-gray-600">No open findings.</p>
        ) : (
          <ul className="space-y-2">
            {openFindings.slice(0, 5).map((f) => (
              <li key={f.id} className="flex items-center justify-between text-sm">
                <span className="text-gray-300">{f.title}</span>
                <SeverityBadge severity={f.severity} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
