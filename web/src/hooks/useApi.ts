import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiGet } from "../api/client";

const STATIC = { staleTime: Infinity, placeholderData: keepPreviousData } as const;

export const useHealth = () =>
  useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => apiGet("/api/v1/health", undefined, signal),
    staleTime: Infinity,
  });

export const useDecision = (deliveryDate: string | undefined, cutoff: string) =>
  useQuery({
    queryKey: ["decision", deliveryDate, cutoff],
    queryFn: ({ signal }) =>
      apiGet("/api/v1/decision", { delivery_date: deliveryDate!, cutoff_local: cutoff }, signal),
    enabled: !!deliveryDate,
    ...STATIC,
  });

export const useSeries = (start: string, end: string, horizon: number) =>
  useQuery({
    queryKey: ["series", start, end, horizon],
    queryFn: ({ signal }) => apiGet("/api/v1/series", { start, end, horizon_h: horizon }, signal),
    ...STATIC,
  });

export const useSummary = (q: {
  start?: string;
  end?: string;
  horizon_h?: number;
  mode?: "horizon" | "decision";
  cutoff_local?: string;
}) =>
  useQuery({
    queryKey: ["summary", q],
    queryFn: ({ signal }) => apiGet("/api/v1/accuracy/summary", q, signal),
    ...STATIC,
  });

export const useByHorizon = (start?: string, end?: string) =>
  useQuery({
    queryKey: ["by-horizon", start, end],
    queryFn: ({ signal }) => apiGet("/api/v1/accuracy/by-horizon", { start, end }, signal),
    ...STATIC,
  });

export const useByHour = (horizon: number, start?: string, end?: string) =>
  useQuery({
    queryKey: ["by-hour", horizon, start, end],
    queryFn: ({ signal }) =>
      apiGet("/api/v1/accuracy/by-hour", { horizon_h: horizon, start, end }, signal),
    ...STATIC,
  });

export const useByLevel = (horizon: number, start?: string, end?: string) =>
  useQuery({
    queryKey: ["by-level", horizon, start, end],
    queryFn: ({ signal }) =>
      apiGet("/api/v1/accuracy/by-level", { horizon_h: horizon, start, end }, signal),
    ...STATIC,
  });

export const useDistribution = (horizon: number, start?: string, end?: string) =>
  useQuery({
    queryKey: ["distribution", horizon, start, end],
    queryFn: ({ signal }) =>
      apiGet("/api/v1/accuracy/distribution", { horizon_h: horizon, start, end, bins: 30 }, signal),
    ...STATIC,
  });

export const useWorstMisses = (cutoff: string) =>
  useQuery({
    queryKey: ["worst", cutoff],
    queryFn: ({ signal }) =>
      apiGet(
        "/api/v1/accuracy/worst-misses",
        { mode: "decision", cutoff_local: cutoff, limit: 10 },
        signal,
      ),
    ...STATIC,
  });

export const useReliability = (cutoff: string) =>
  useQuery({
    queryKey: ["reliability", cutoff],
    queryFn: ({ signal }) => apiGet("/api/v1/reliability", { cutoff_local: cutoff }, signal),
    ...STATIC,
  });

export const useDataQuality = (cutoff: string) =>
  useQuery({
    queryKey: ["dq", cutoff],
    queryFn: ({ signal }) => apiGet("/api/v1/data-quality", { cutoff_local: cutoff }, signal),
    ...STATIC,
  });
