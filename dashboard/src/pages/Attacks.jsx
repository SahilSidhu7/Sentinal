import { useEffect, useState } from 'react'
import { getAttacks, getBans, banIp } from '../lib/api'

export default function Attacks() {
  const [attacks, setAttacks] = useState([])
  const [bans, setBans] = useState([])

  useEffect(() => {
    getAttacks().then(setAttacks)
    getBans().then(setBans)
  }, [])

  const bannedIps = new Set(bans.filter((b) => !b.reversed_at).map((b) => b.ip))

  async function handleBan(attack) {
    await banIp(attack.id, 3600)
    setBans((prev) => [...prev, { ip: attack.source_ip, mode: 'manual', ttl_expires_at: null, reversed_at: null }])
  }

  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900/50">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-gray-800 text-gray-500">
          <tr>
            <th className="px-4 py-2 font-medium">Source IP</th>
            <th className="px-4 py-2 font-medium">Attack type</th>
            <th className="px-4 py-2 font-medium">Confidence</th>
            <th className="px-4 py-2 font-medium">Status</th>
            <th className="px-4 py-2 font-medium" />
          </tr>
        </thead>
        <tbody>
          {attacks.map((a) => (
            <tr key={a.id} className="border-b border-gray-800/50">
              <td className="px-4 py-2 font-mono text-gray-200">{a.source_ip}</td>
              <td className="px-4 py-2 text-gray-300 capitalize">{a.attack_type_guess.replace('_', ' ')}</td>
              <td className="px-4 py-2 text-gray-400">{Math.round(a.confidence * 100)}%</td>
              <td className="px-4 py-2 text-gray-400 capitalize">{a.status}</td>
              <td className="px-4 py-2 text-right">
                {bannedIps.has(a.source_ip) ? (
                  <span className="text-xs text-red-400">Banned</span>
                ) : (
                  <button
                    className="rounded border border-red-800 px-2 py-1 text-xs text-red-400 hover:bg-red-950/40"
                    onClick={() => handleBan(a)}
                  >
                    Ban IP
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
