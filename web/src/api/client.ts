// Typed API client. Types are generated from the FastAPI OpenAPI schema (npm run gen:api),
// so a backend contract change breaks this build instead of production.
import type { components, paths } from "./schema";

export type Schemas = components["schemas"];
export type Metrics = Schemas["MetricsBlock"];
export type Meta = Schemas["Meta"];

type GetPath = { [P in keyof paths]: paths[P] extends { get: unknown } ? P : never }[keyof paths];
type Op<P extends GetPath> = paths[P]["get"];
type QueryOf<P extends GetPath> = Op<P> extends { parameters: { query?: infer Q } } ? Q : never;
type JsonOf<P extends GetPath> =
  Op<P> extends {
    responses: { 200: { content: { "application/json": infer R } } };
  }
    ? R
    : never;

export const API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export function buildUrl(path: string, query?: Record<string, unknown>): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(query ?? {})) {
    if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  }
  const s = qs.toString();
  return `${API_BASE}${path}${s ? `?${s}` : ""}`;
}

export async function apiGet<P extends GetPath>(
  path: P,
  query?: QueryOf<P>,
  signal?: AbortSignal,
): Promise<JsonOf<P>> {
  const res = await fetch(buildUrl(path, query as Record<string, unknown>), { signal });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: unknown };
      detail =
        typeof body.detail === "string"
          ? body.detail
          : Array.isArray(body.detail)
            ? body.detail.map((d: { msg?: string }) => d.msg).join("; ")
            : detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as JsonOf<P>;
}
