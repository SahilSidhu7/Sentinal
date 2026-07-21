import { useEffect, useState } from 'react'
import { getFindings, dismissFinding } from '../lib/api'
import SeverityBadge from '../components/SeverityBadge'

export default function Findings() {
  const [findings, setFindings] = useState([])
  const [expanded, setExpanded] = useState(null)

  useEffect(() => {
    getFindings().then(setFindings)
  }, [])

  async function handleDismiss(id) {
    await dismissFinding(id)
    setFindings((prev) => prev.map((f) => (f.id === id ? { ...f, status: 'dismissed' } : f)))
  }

  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900/50">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-gray-800 text-gray-500">
          <tr>
            <th className="px-4 py-2 font-medium">Finding</th>
            <th className="px-4 py-2 font-medium">Severity</th>
            <th className="px-4 py-2 font-medium">File</th>
            <th className="px-4 py-2 font-medium">Status</th>
            <th className="px-4 py-2 font-medium" />
          </tr>
        </thead>
        <tbody>
          {findings.map((f) => (
            <>
              <tr
                key={f.id}
                className="cursor-pointer border-b border-gray-800/50 hover:bg-gray-800/30"
                onClick={() => setExpanded(expanded === f.id ? null : f.id)}
              >
                <td className="px-4 py-2 text-gray-200">{f.title}</td>
                <td className="px-4 py-2">
                  <SeverityBadge severity={f.severity} />
                </td>
                <td className="px-4 py-2 font-mono text-xs text-gray-500">{f.file}</td>
                <td className="px-4 py-2 text-gray-400 capitalize">{f.status}</td>
                <td className="px-4 py-2 text-right">
                  {f.status === 'open' && (
                    <button
                      className="rounded border border-gray-700 px-2 py-1 text-xs text-gray-300 hover:bg-gray-800"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDismiss(f.id)
                      }}
                    >
                      Dismiss
                    </button>
                  )}
                </td>
              </tr>
              {expanded === f.id && (
                <tr key={`${f.id}-detail`} className="border-b border-gray-800/50 bg-gray-950/40">
                  <td colSpan={5} className="px-4 py-3 text-sm text-gray-400">
                    <p>{f.explanation}</p>
                    <p className="mt-1 text-gray-500">Suggested fix: {f.suggested_fix}</p>
                  </td>
                </tr>
              )}
            </>
          ))}
        </tbody>
      </table>
    </div>
  )
}
