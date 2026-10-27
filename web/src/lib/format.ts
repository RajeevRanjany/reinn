// Formatting helpers. Data is UTC; everything a person reads is Europe/London.
export const TZ = "Europe/London";

const dtFmt = new Intl.DateTimeFormat("en-GB", {
  timeZone: TZ,
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});
const timeFmt = new Intl.DateTimeFormat("en-GB", {
  timeZone: TZ,
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});
const dayFmt = new Intl.DateTimeFormat("en-GB", {
  timeZone: TZ,
  weekday: "short",
  day: "numeric",
  month: "short",
  year: "numeric",
});

export const fmtDateTime = (iso: string | null | undefined): string =>
  iso ? dtFmt.format(new Date(iso)) : "–";
export const fmtTime = (iso: string | null | undefined): string =>
  iso ? timeFmt.format(new Date(iso)) : "–";
export const fmtDay = (isoDate: string): string => dayFmt.format(new Date(`${isoDate}T12:00:00Z`));

export function fmtNum(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  return v.toLocaleString("en-GB", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

export function fmtMW(v: number | null | undefined, signed = false): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  const s = fmtNum(Math.abs(v));
  const sign = v < 0 ? "−" : signed && v > 0 ? "+" : "";
  return `${sign}${s} MW`;
}

/** Compact MWh: 278,630 -> "278.6 GWh"; below 10 GWh shown in MWh. */
export function fmtEnergy(mwh: number | null | undefined): string {
  if (mwh === null || mwh === undefined || Number.isNaN(mwh)) return "–";
  if (Math.abs(mwh) >= 10_000) return `${fmtNum(mwh / 1000, 1)} GWh`;
  return `${fmtNum(mwh)} MWh`;
}

export function fmtPct(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  return `${(v * 100).toFixed(digits)}%`;
}

export function fmtMinutes(min: number | null | undefined): string {
  if (min === null || min === undefined) return "–";
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  return h ? `${h}h ${m.toString().padStart(2, "0")}m` : `${m} min`;
}

/** ISO date (YYYY-MM-DD) shifted by n days. */
export function addDays(isoDate: string, n: number): string {
  const d = new Date(`${isoDate}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}
