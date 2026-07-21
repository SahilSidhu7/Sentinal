import { Link } from "react-router-dom";
import { Badge } from "../components/Badge";
import { TerminalPreview } from "../components/TerminalPreview";
import { NumberedCard } from "../components/NumberedCard";
import { ArchitectureDiagram } from "../components/ArchitectureDiagram";
import { FaqCard } from "../components/FaqCard";
import { ActIcon, DetectIcon, ScanIcon, ShowIcon } from "../components/icons";

const PROBLEMS = [
  {
    number: "01",
    title: "Cloud tools ship your data out",
    description:
      "Most monitoring SaaS routes your logs through a third-party pipeline before you ever see them. Your incident data becomes someone else's dataset.",
  },
  {
    number: "02",
    title: "Alerts arrive after the damage",
    description:
      "By the time a dashboard tab refreshes, the breach already happened. Detection has to run where the data lives, not after an upload round-trip.",
  },
  {
    number: "03",
    title: "Auto-remediation causes outages",
    description:
      "Kill switches that trigger with no human in the loop have taken down more services than the attacks they were meant to stop.",
  },
];

const FEATURES = [
  {
    title: "Scan",
    description: "Secret detection and dependency CVE lookups across any target.",
    icon: ScanIcon,
  },
  {
    title: "Detect",
    description: "Local Drain3 + ONNX + Isolation Forest anomaly scoring, no LLM.",
    icon: DetectIcon,
  },
  {
    title: "Show",
    description: "Live security score, findings, and attack feed over WebSocket.",
    icon: ShowIcon,
  },
  {
    title: "Act",
    description: "Human-approved response by default, opt-in reversible auto-ban.",
    icon: ActIcon,
  },
];

const TRUST_POINTS = [
  {
    title: "Raw logs never leave your machine",
    description:
      "Only structured findings and anomaly scores cross the wire to the core backend — never raw log lines.",
  },
  {
    title: "No LLM in the detection path",
    description:
      "Drain3 parsing, ONNX MiniLM embeddings, and Isolation Forest scoring all run locally, CPU-only.",
  },
  {
    title: "Bans execute agent-side",
    description:
      "IP banning is scoped to the agent's own network namespace — the core backend can request one, never force it.",
  },
];

const FAQS = [
  {
    question: "Does this replace a SIEM?",
    answer:
      "No. Sentinal is a lightweight, local-first companion for self-hosted setups and small servers — not a full enterprise SIEM replacement.",
  },
  {
    question: "What data leaves my machine?",
    answer:
      "Only structured findings, anomaly scores, and metadata cross the wire to the core backend. Raw log lines stay on the agent's host.",
  },
  {
    question: "Can I run this without Docker?",
    answer:
      "Docker Compose is the supported quickstart, but the core backend is just FastAPI + SQLite underneath, so a bare-metal setup is possible.",
  },
  {
    question: "Is auto-response actually automatic?",
    answer:
      "Manual-confirm is the default for every action. Auto-ban is opt-in per target and only fires on sustained, high-confidence anomaly scores.",
  },
];

export function Home() {
  return (
    <div>
      <section className="mx-auto max-w-4xl px-6 py-24 text-center">
        <div className="mb-6 flex justify-center">
          <Badge>Local-first security monitoring</Badge>
        </div>
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
        <div className="mt-12">
          <TerminalPreview lines={["docker-compose up -d"]} />
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-20">
        <h2 className="text-center text-3xl font-bold tracking-tight text-white sm:text-4xl">
          Security tools that watch you back.
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-center text-sm text-slate-400">
          Most monitoring platforms ask you to trust a stranger with your incident data. Sentinal
          doesn't ask.
        </p>
        <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-3">
          {PROBLEMS.map((problem) => (
            <NumberedCard key={problem.number} {...problem} />
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-20">
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((feature) => {
            const Icon = feature.icon;
            return (
              <div
                key={feature.title}
                className="rounded-xl border border-slate-800 bg-slate-900/60 p-6"
              >
                <div className="mb-4 flex h-9 w-9 items-center justify-center rounded-lg bg-sky-500/10 text-sky-400">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="text-base font-bold text-white">{feature.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-slate-400">
                  {feature.description}
                </p>
              </div>
            );
          })}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-20">
        <h2 className="text-center text-2xl font-bold text-white">Why local-first</h2>
        <p className="mx-auto mt-3 max-w-xl text-center text-sm text-slate-400">
          Not a promise — a boundary built into the architecture.
        </p>
        <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-3">
          {TRUST_POINTS.map((point) => (
            <div key={point.title} className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
              <h3 className="text-base font-semibold text-white">{point.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">{point.description}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-20">
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-10">
          <h2 className="text-center text-2xl font-semibold text-white">Two deployable pieces</h2>
          <p className="mx-auto mt-3 max-w-2xl text-center text-sm text-slate-400">
            Run the core backend and dashboard with{" "}
            <code className="text-slate-300">docker-compose</code>. Deploy the lightweight
            sentinel-agent alongside your own servers — it detects locally and ships only
            findings and scores back.
          </p>
          <div className="mt-10">
            <ArchitectureDiagram />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-4xl px-6 py-20">
        <h2 className="text-center text-2xl font-bold text-white">FAQ</h2>
        <div className="mt-10 grid grid-cols-1 gap-6 sm:grid-cols-2">
          {FAQS.map((faq) => (
            <FaqCard key={faq.question} question={faq.question} answer={faq.answer} />
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-4xl px-6 py-24 text-center">
        <h2 className="text-4xl font-bold tracking-tight text-white sm:text-5xl">
          Run your own security monitoring.
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-lg text-slate-400">
          Self-hosted, open-source, no data leaves your infrastructure.
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
    </div>
  );
}
