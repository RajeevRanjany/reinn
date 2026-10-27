// Chart tokens per mode. Values follow a validated categorical palette (adjacent-pair CVD
// ΔE ≥ 9). Text never wears a series colour; series are also told apart by dash style.
import { useSyncExternalStore } from "react";

export type Mode = "light" | "dark";

export const TOKENS = {
  light: {
    surface: "#fcfcfb",
    text: "#0b0b0b",
    text2: "#52514e",
    muted: "#898781",
    grid: "#e1e0d9",
    axis: "#c3c2b7",
    forecast: "#2a78d6",
    actual: "#eb6834",
    baseline: "#1baf7a",
    band: "rgba(42,120,214,0.16)",
    vintage: "#9a9890",
    over: "#d03b3b",
    under: "#2a78d6",
  },
  dark: {
    surface: "#1a1a19",
    text: "#f0efec",
    text2: "#c3c2b7",
    muted: "#898781",
    grid: "#2c2c2a",
    axis: "#383835",
    forecast: "#3987e5",
    actual: "#d95926",
    baseline: "#199e70",
    band: "rgba(57,135,229,0.22)",
    vintage: "#6b6a64",
    over: "#e66767",
    under: "#3987e5",
  },
} as const;

export type Tokens = (typeof TOKENS)[Mode];

const media = () => window.matchMedia("(prefers-color-scheme: dark)");

export function resolvedMode(): Mode {
  const attr = document.documentElement.dataset.theme;
  if (attr === "light" || attr === "dark") return attr;
  return media().matches ? "dark" : "light";
}

function subscribe(cb: () => void) {
  const mq = media();
  mq.addEventListener("change", cb);
  const obs = new MutationObserver(cb);
  obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  return () => {
    mq.removeEventListener("change", cb);
    obs.disconnect();
  };
}

export function useMode(): Mode {
  return useSyncExternalStore(subscribe, resolvedMode, () => "light");
}

export function useTokens(): Tokens {
  return TOKENS[useMode()];
}
