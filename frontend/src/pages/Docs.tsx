import { Reveal } from "../components/Reveal";

const SECTIONS = [
  {
    id: "overview",
    title: "Overview",
    body: [
      "Sentinal watches a target (folder, repo, or container), scans it for security issues, detects live attacks, visualizes risk on a live dashboard, and takes safe, human-approved response actions.",
      "Core loop: Watch → Scan → Detect (Drain3 + ONNX + Isolation Forest) → Show (Dashboard) → Act (auto-response).",
    ],
  },
  {
    id: "architecture",
    title: "Architecture",
    body: [
      "Two deployable units: the core backend + dashboard (FastAPI, SQLite, WebSocket), and a separate minimal sentinel-agent you run alongside your own servers.",
      "The agent tails logs, runs the anomaly pipeline locally, and ships only structured findings and scores to the core backend — raw logs never leave your infrastructure.",
    ],
  },
  {
    id: "detection",
    title: "Detection pipeline",
    body: [
      "High-volume log lines are parsed into templates with Drain3, embedded with all-MiniLM-L6-v2 via ONNX Runtime (CPU-only, no PyTorch), and scored with a per-target Isolation Forest trained on that target's own rolling normal traffic.",
      "There is no LLM anywhere in the detection or explanation path. Finding explanations resolve against a static rule-template table.",
    ],
  },
  {
    id: "response",
    title: "Auto-response & IP banning",
    body: [
      "Critical findings always produce an audit-log entry and a dashboard alert. IP banning is manual-confirm by default.",
      "Opt-in auto-ban requires sustained high-confidence anomaly scores and executes agent-side, scoped to that agent's own network namespace — never core-backend-initiated. Bans are TTL-based and reversible.",
    ],
  },
  {
    id: "audit",
    title: "Audit log",
    body: [
      "Every finding lifecycle event and every action (ban, unban, dismiss, fix-applied) is written to an append-only audit log with a chained hash (prev_hash → entry_hash) so tampering is at least detectable.",
    ],
  },
];

export function Docs() {
  return (
    <div className="mx-auto flex max-w-6xl gap-10 px-6 py-16">
      <aside className="hidden w-48 flex-shrink-0 lg:block">
        <nav className="sticky top-8 space-y-1 text-sm">
          {SECTIONS.map((section) => (
            <a
              key={section.id}
              href={`#${section.id}`}
              className="block rounded-md px-3 py-1.5 text-slate-400 transition-colors duration-200 ease-out hover:bg-slate-800/60 hover:text-slate-200"
            >
              {section.title}
            </a>
          ))}
        </nav>
      </aside>

      <div className="min-w-0 flex-1 space-y-12">
        <Reveal as="h1" className="text-2xl font-semibold text-white">
          Documentation
        </Reveal>
        {SECTIONS.map((section, i) => (
          <Reveal key={section.id} as="section" delayMs={i === 0 ? 80 : 0} id={section.id} className="scroll-mt-8">
            <h2 className="mb-3 text-lg font-semibold text-white">{section.title}</h2>
            <div className="space-y-3 text-sm leading-relaxed text-slate-400">
              {section.body.map((paragraph, i) => (
                <p key={i}>{paragraph}</p>
              ))}
            </div>
          </Reveal>
        ))}
      </div>
    </div>
  );
}
