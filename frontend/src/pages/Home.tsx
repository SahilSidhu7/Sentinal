import { Link } from "react-router-dom";

const FEATURES = [
  {
    title: "Scan",
    description:
      "Secret detection (regex + entropy) and dependency CVE lookups across any folder, repo, or container target.",
  },
  {
    title: "Detect",
    description:
      "Drain3 log parsing + ONNX MiniLM embeddings + Isolation Forest anomaly scoring — fully local, no LLM in the detection path.",
  },
  {
    title: "Show",
    description:
      "A live dashboard with a security score, findings by severity, and a real-time attack feed over WebSocket.",
  },
  {
    title: "Act",
    description:
      "Human-approved response actions by default, with opt-in auto IP-banning under strict, reversible, TTL-based conditions.",
  },
];

export function Home() {
  return (
    <div>
      <section className="mx-auto max-w-4xl px-6 py-24 text-center">
        <h1 className="text-4xl font-bold tracking-tight text-white sm:text-5xl">
          Security monitoring for the machines you actually run.
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-slate-400">
          Sentinal watches your local machine or self-hosted server, scans it for security
          issues, detects live attacks with a fully local anomaly pipeline, and gives you a
          dashboard to see and respond to it all — without shipping your raw logs anywhere.
        </p>
        <div className="mt-10 flex justify-center gap-4">
          <Link
            to="/install"
            className="rounded-md bg-sky-500 px-5 py-2.5 text-sm font-medium text-white hover:bg-sky-400"
          >
            Get started
          </Link>
          <Link
            to="/docs"
            className="rounded-md border border-slate-700 px-5 py-2.5 text-sm font-medium text-slate-200 hover:bg-slate-800"
          >
            Read the docs
          </Link>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-16">
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((feature) => (
            <div
              key={feature.title}
              className="rounded-xl border border-slate-800 bg-slate-900/60 p-6"
            >
              <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-sky-400">
                {feature.title}
              </h3>
              <p className="text-sm text-slate-400">{feature.description}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-16">
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-10 text-center">
          <h2 className="text-2xl font-semibold text-white">Two deployable pieces</h2>
          <p className="mx-auto mt-3 max-w-2xl text-sm text-slate-400">
            A core backend + dashboard you run with <code className="text-slate-300">docker-compose</code>,
            and a lightweight sentinel-agent you deploy alongside your own servers. The agent tails
            logs and runs detection locally — only structured findings and scores ever cross the
            wire, never raw log lines.
          </p>
        </div>
      </section>
    </div>
  );
}
