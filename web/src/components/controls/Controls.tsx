import { useEffect, useMemo, useState } from "react";
import { debounce } from "../../lib/chartData";
import { addDays, fmtDay } from "../../lib/format";

export function HorizonSlider({
  value,
  onChange,
}: {
  value: number;
  onChange: (h: number) => void;
}) {
  // Local state moves instantly; the request is debounced (~250 ms).
  const [local, setLocal] = useState(value);
  useEffect(() => setLocal(value), [value]);
  const commit = useMemo(() => debounce(onChange, 250), [onChange]);
  return (
    <label className="control control-slider">
      <span className="control-label">
        Forecast horizon <strong>{local}h</strong>
      </span>
      <input
        type="range"
        min={0}
        max={48}
        step={1}
        value={local}
        aria-valuetext={`${local} hours ahead`}
        onChange={(e) => {
          const h = Number(e.target.value);
          setLocal(h);
          commit(h);
        }}
      />
      <span className="slider-scale" aria-hidden>
        <span>0h</span>
        <span>12h</span>
        <span>24h</span>
        <span>36h</span>
        <span>48h</span>
      </span>
    </label>
  );
}

export function DayPicker({
  value,
  days,
  onChange,
}: {
  value: string;
  days: string[];
  onChange: (d: string) => void;
}) {
  const i = days.indexOf(value);
  return (
    <div className="control">
      <span className="control-label">Delivery day (D)</span>
      <div className="day-picker">
        <button
          type="button"
          aria-label="Previous day"
          disabled={i <= 0}
          onClick={() => onChange(days[i - 1]!)}
        >
          ‹
        </button>
        <select value={value} onChange={(e) => onChange(e.target.value)}>
          {days.map((d) => (
            <option key={d} value={d}>
              {fmtDay(d)}
            </option>
          ))}
        </select>
        <button
          type="button"
          aria-label="Next day"
          disabled={i < 0 || i >= days.length - 1}
          onClick={() => onChange(days[i + 1]!)}
        >
          ›
        </button>
      </div>
    </div>
  );
}

export function CutoffPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (c: string) => void;
}) {
  return (
    <label className="control">
      <span className="control-label">Decision cutoff (D−1, UK time)</span>
      <input
        type="time"
        step={900}
        value={value}
        onChange={(e) => e.target.value && onChange(e.target.value)}
      />
    </label>
  );
}

export function DateRange({
  start,
  end,
  min,
  max,
  onChange,
}: {
  start: string;
  end: string;
  min: string;
  max: string;
  onChange: (start: string, end: string) => void;
}) {
  // `end` is an exclusive bound for the API; the picker shows the inclusive last day.
  const lastDay = addDays(end, -1);
  return (
    <div className="control">
      <span className="control-label">Target dates (UK)</span>
      <div className="range">
        <input
          type="date"
          aria-label="From"
          min={min}
          max={lastDay}
          value={start}
          onChange={(e) => e.target.value && onChange(e.target.value, end)}
        />
        <span aria-hidden>→</span>
        <input
          type="date"
          aria-label="To (inclusive)"
          min={start}
          max={max}
          value={lastDay}
          onChange={(e) => e.target.value && onChange(start, addDays(e.target.value, 1))}
        />
      </div>
    </div>
  );
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div className="segmented" role="radiogroup" aria-label={label}>
      {options.map((o) => (
        <button
          type="button"
          key={o.value}
          role="radio"
          aria-checked={value === o.value}
          className={value === o.value ? "on" : ""}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
