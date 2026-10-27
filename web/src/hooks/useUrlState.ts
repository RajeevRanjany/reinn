import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";

/** View state lives in the URL (?date=…&h=…) so a view can be shared with a colleague. */
export function useUrlState() {
  const [params, setParams] = useSearchParams();
  const get = useCallback((key: string) => params.get(key), [params]);
  const set = useCallback(
    (patch: Record<string, string | number | null>) =>
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          for (const [k, v] of Object.entries(patch)) {
            if (v === null || v === "") next.delete(k);
            else next.set(k, String(v));
          }
          return next;
        },
        { replace: true },
      ),
    [setParams],
  );
  return { get, set };
}
