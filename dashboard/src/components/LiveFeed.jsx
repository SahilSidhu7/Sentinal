export default function LiveFeed({ events }) {
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-4">
      <h2 className="mb-2 text-sm font-medium text-gray-400">Live feed</h2>
      {events.length === 0 ? (
        <p className="text-sm text-gray-600">No events yet.</p>
      ) : (
        <ul className="space-y-1.5 text-sm">
          {events.slice(0, 20).map((e, i) => (
            <li key={i} className="flex gap-2 text-gray-300">
              <span className="text-gray-600">{new Date(e.detected_at ?? e.t ?? Date.now()).toLocaleTimeString()}</span>
              <span>{e.title ?? e.attack_type_guess ?? e.type ?? 'event'}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
