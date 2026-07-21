import { NavLink, Outlet } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/", label: "Home" },
  { to: "/docs", label: "Docs" },
  { to: "/install", label: "Installation" },
];

export function SiteLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/60">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <NavLink to="/" className="text-lg font-semibold tracking-tight text-white">
            Sentinal
          </NavLink>
          <nav className="flex items-center gap-1">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-slate-800 text-white"
                      : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <a
            href="https://github.com/SahilSidhu7/Sentinal"
            target="_blank"
            rel="noreferrer"
            className="rounded-md border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800"
          >
            GitHub
          </a>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t border-slate-800 py-10">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-4 px-6 text-center">
          <nav className="flex items-center gap-6 text-sm text-slate-400">
            <NavLink to="/docs" className="hover:text-slate-200">
              Docs
            </NavLink>
            <NavLink to="/install" className="hover:text-slate-200">
              Installation
            </NavLink>
            <a
              href="https://github.com/SahilSidhu7/Sentinal"
              target="_blank"
              rel="noreferrer"
              className="hover:text-slate-200"
            >
              GitHub
            </a>
            <a
              href="https://github.com/SahilSidhu7/Sentinal/blob/main/LICENSE"
              target="_blank"
              rel="noreferrer"
              className="hover:text-slate-200"
            >
              License
            </a>
          </nav>
          <p className="text-xs text-slate-500">
            Sentinal — local-first security monitoring, no LLM in the detection path.
          </p>
        </div>
      </footer>
    </div>
  );
}
