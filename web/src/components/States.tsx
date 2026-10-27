import type { ReactNode } from "react";
import { ApiError } from "../api/client";

export function Loading({ label = "Loading…", height = 360 }: { label?: string; height?: number }) {
  return (
    <div className="state state-loading" style={{ minHeight: height }} aria-busy="true">
      <span className="spinner" aria-hidden /> {label}
    </div>
  );
}

export function ErrorState({ error, height = 200 }: { error: unknown; height?: number }) {
  const msg =
    error instanceof ApiError
      ? `${error.message} (HTTP ${error.status})`
      : error instanceof Error
        ? error.message
        : "Something went wrong.";
  const network = error instanceof TypeError;
  return (
    <div className="state state-error" role="alert" style={{ minHeight: height }}>
      <strong>Couldn’t load this view.</strong>
      <span>{network ? "The API is unreachable. If it was asleep, retry in ~20 s." : msg}</span>
    </div>
  );
}

export function Empty({ children, height = 200 }: { children: ReactNode; height?: number }) {
  return (
    <div className="state" style={{ minHeight: height }}>
      {children}
    </div>
  );
}

export function Panel({
  title,
  subtitle,
  actions,
  children,
}: {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="panel">
      <header className="panel-head">
        <div>
          <h2>{title}</h2>
          {subtitle && <p className="panel-sub">{subtitle}</p>}
        </div>
        {actions && <div className="panel-actions">{actions}</div>}
      </header>
      {children}
    </section>
  );
}

export function SignNote() {
  return (
    <p className="sign-note">
      Error = forecast − actual. <strong>Positive = over-forecast</strong> → less wind than planned
      → the buyer is short.
    </p>
  );
}
