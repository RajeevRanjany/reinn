// Pure mappings from API payloads to chart series. Kept free of React/ECharts so they are
// trivially unit-testable.

export type Pt = [number, number | null];

interface DecisionPointLike {
  target_time: string;
  forecast_mw: number | null;
  p10_mw: number | null;
  p90_mw: number | null;
}

const t = (iso: string) => new Date(iso).getTime();

/** ECharts draws a band as two stacked areas: an invisible lower line + (upper - lower). */
export function bandSeries(points: DecisionPointLike[]): { lower: Pt[]; width: Pt[] } {
  const lower: Pt[] = [];
  const width: Pt[] = [];
  for (const p of points) {
    const ok = p.p10_mw !== null && p.p90_mw !== null;
    lower.push([t(p.target_time), ok ? p.p10_mw : null]);
    width.push([t(p.target_time), ok ? (p.p90_mw as number) - (p.p10_mw as number) : null]);
  }
  return { lower, width };
}

export function lineSeries<T extends { target_time: string }>(rows: T[], key: keyof T): Pt[] {
  return rows.map((r) => {
    const v = r[key];
    return [t(r.target_time), typeof v === "number" ? v : null];
  });
}

/** Drop null points so a sparse (hourly) series is drawn as a connected line. */
export const dense = (pts: Pt[]): Pt[] => pts.filter((p) => p[1] !== null);

/** Debounce for slider-driven requests. */
export function debounce<A extends unknown[]>(fn: (...a: A) => void, ms: number) {
  let id: ReturnType<typeof setTimeout> | undefined;
  return (...a: A) => {
    if (id) clearTimeout(id);
    id = setTimeout(() => fn(...a), ms);
  };
}

/** Clamp a horizon value into 0..48 integer hours (URL params can be anything). */
export function clampHorizon(raw: string | null, fallback = 24): number {
  const n = Number(raw);
  if (raw === null || raw === "" || !Number.isFinite(n)) return fallback;
  return Math.min(48, Math.max(0, Math.round(n)));
}
