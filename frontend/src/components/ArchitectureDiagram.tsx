export function ArchitectureDiagram() {
  return (
    <div className="flex flex-col items-center gap-3 text-sm sm:flex-row sm:justify-center sm:gap-0">
      <div className="w-full max-w-[220px] rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-center">
        <p className="font-semibold text-white">Your server</p>
        <p className="mt-1 text-xs text-slate-500">sentinel-agent</p>
        <p className="mt-2 text-xs text-slate-400">tails logs, runs detection locally</p>
      </div>

      <div className="flex flex-col items-center px-4 text-slate-500 sm:rotate-0">
        <span className="hidden font-mono text-xs sm:block">findings + scores only</span>
        <span className="text-lg sm:hidden">↓</span>
        <span className="hidden text-lg sm:block">→</span>
        <span className="font-mono text-xs sm:hidden">findings + scores only</span>
      </div>

      <div className="w-full max-w-[220px] rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-center">
        <p className="font-semibold text-white">Your infra</p>
        <p className="mt-1 text-xs text-slate-500">core backend + dashboard</p>
        <p className="mt-2 text-xs text-slate-400">FastAPI, SQLite, live WebSocket feed</p>
      </div>
    </div>
  );
}
