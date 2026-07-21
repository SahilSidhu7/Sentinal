export function TerminalPreview({ lines }: { lines: string[] }) {
  return (
    <div className="mx-auto max-w-xl overflow-hidden rounded-xl border border-slate-800 bg-slate-900/80 text-left shadow-2xl shadow-black/40">
      <div className="flex items-center gap-1.5 border-b border-slate-800 bg-slate-900 px-4 py-2.5">
        <span className="h-2.5 w-2.5 rounded-full bg-red-500/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-yellow-500/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-green-500/70" />
        <span className="ml-3 text-xs text-slate-500">quickstart</span>
      </div>
      <div className="px-4 py-4 font-mono text-sm">
        {lines.map((line, i) => (
          <div key={i} className="flex gap-2">
            <span className="text-slate-500">$</span>
            <span className="text-slate-200">{line}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
