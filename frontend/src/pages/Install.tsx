const STEPS = [
  {
    title: "1. Clone the repo",
    code: "git clone https://github.com/SahilSidhu7/Sentinal.git\ncd Sentinal",
  },
  {
    title: "2. Start the core stack",
    code: "docker-compose up -d",
    note: "Brings up the FastAPI backend, dashboard, and SQLite storage.",
  },
  {
    title: "3. Log in",
    code: "open http://localhost:8000",
    note: "Single-admin MVP — sign in with the admin credentials printed on first boot.",
  },
  {
    title: "4. Deploy the sentinel-agent on a target server",
    code: "docker run -d \\\n  --name sentinal-agent \\\n  -v /path/to/target:/target:ro \\\n  sentinal/agent",
    note: "The agent tails logs and runs detection locally; only structured findings/scores are sent to the core backend.",
  },
  {
    title: "5. Register the target",
    code: 'curl -X POST http://localhost:8000/targets \\\n  -H "Authorization: Bearer $TOKEN" \\\n  -d \'{"name": "my-server", "kind": "container"}\'',
  },
];

export function Install() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="mb-3 text-2xl font-semibold text-white">Installation</h1>
      <p className="mb-10 text-sm text-slate-400">
        Requires Docker and docker-compose. Scapy packet sniffing and OSV.dev CVE lookups degrade
        gracefully if you're offline or unprivileged — everything else works out of the box.
      </p>

      <div className="space-y-8">
        {STEPS.map((step) => (
          <div key={step.title}>
            <h2 className="mb-2 text-sm font-semibold text-white">{step.title}</h2>
            <pre className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-950 p-4 text-xs text-slate-300">
              {step.code}
            </pre>
            {step.note && <p className="mt-2 text-xs text-slate-500">{step.note}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}
