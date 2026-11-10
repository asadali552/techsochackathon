import { useEffect, useRef, useState } from "react";

type LoadState<T> =
  | { status: "idle" }
  | { status: "loading"; previous?: T }
  | { status: "success"; data: T }
  | { status: "error"; message: string };

export function useMapData<T>(key: string | null, load: (signal: AbortSignal) => Promise<T>, retainedScope?: string) {
  const [result, setResult] = useState<{ key: string; state: LoadState<T> }>();
  const [lastSuccess, setLastSuccess] = useState<{ scope: string; data: T }>();
  const cache = useRef(new Map<string, { data: T; fetchedAt: number }>());
  useEffect(() => {
    if (key === null) return;
    const save = (data: T) => {
      setResult({ key, state: { status: "success", data } });
      if (retainedScope !== undefined) setLastSuccess({ scope: retainedScope, data });
    };
    const stored = cache.current.get(key);
    if (retainedScope !== undefined && stored && Date.now() - stored.fetchedAt < 30_000) {
      save(stored.data);
      return;
    }
    const controller = new AbortController();
    load(controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        if (retainedScope !== undefined) {
          cache.current.delete(key);
          cache.current.set(key, { data, fetchedAt: Date.now() });
          if (cache.current.size > 6) cache.current.delete(cache.current.keys().next().value!);
        }
        save(data);
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          const message = error instanceof Error ? error.message : "The map data request failed.";
          setResult({ key, state: { status: "error", message } });
        }
      });
    return () => controller.abort();
  }, [key, load, retainedScope]);

  if (key === null) return { status: "idle" } as const;
  return result?.key === key ? result.state : {
    status: "loading", previous: lastSuccess?.scope === retainedScope ? lastSuccess?.data : undefined,
  } as const;
}
