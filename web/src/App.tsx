import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useHealth } from "./hooks/useApi";
import { fmtDateTime } from "./lib/format";
import { useMode } from "./lib/theme";
import { AccuracyPage } from "./pages/AccuracyPage";
import { DecisionPage } from "./pages/DecisionPage";
import { ReliabilityPage } from "./pages/ReliabilityPage";
import { SeriesPage } from "./pages/SeriesPage";

const NAV = [
  { to: "/decision", label: "Decision Mode" },
  { to: "/series", label: "Forecast vs Actual" },
  { to: "/accuracy", label: "Accuracy Explorer" },
  { to: "/reliability", label: "Reliability & Data" },
];

function ThemeToggle() {
  const mode = useMode();
  const next = mode === "dark" ? "light" : "dark";
  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label={`Switch to ${next} mode`}
      onClick={() => {
        document.documentElement.dataset.theme = next;
        localStorage.setItem("theme", next);
      }}
    >
      {mode === "dark" ? "☀" : "☾"}
    </button>
  );
}

export function App() {
  const health = useHealth();
  const { search } = useLocation();
  // Carry shared params (cutoff) across pages; page-specific ones are harmless.
  const keep = new URLSearchParams(search);
  const carry = keep.get("cutoff") ? `?cutoff=${keep.get("cutoff")}` : "";
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden>
            <rect width="32" height="32" rx="7" fill="currentColor" />
            <path
              d="M6 21c4-8 8-8 10-3s6 5 10-3"
              stroke="var(--surface)"
              strokeWidth="3"
              fill="none"
              strokeLinecap="round"
            />
          </svg>
          <span>Headroom</span>
          <small>Wind forecast risk desk · GB day-ahead</small>
        </div>
        <nav aria-label="Main">
          {NAV.map((n) => (
            <NavLink key={n.to} to={`${n.to}${carry}`}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <ThemeToggle />
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/decision" replace />} />
          <Route path="/decision" element={<DecisionPage />} />
          <Route path="/series" element={<SeriesPage />} />
          <Route path="/accuracy" element={<AccuracyPage />} />
          <Route path="/reliability" element={<ReliabilityPage />} />
          <Route path="*" element={<Navigate to="/decision" replace />} />
        </Routes>
      </main>
      <footer className="footer">
        Data: Elexon BMRS — WINDFOR (forecast) and FUELHH fuelType=WIND (outturn). Times shown in UK
        time. Snapshot {health.data?.data_version ?? "…"}
        {health.data?.built_at ? `, built ${fmtDateTime(health.data.built_at)}` : ""}.
      </footer>
    </div>
  );
}
