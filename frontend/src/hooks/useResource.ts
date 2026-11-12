import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "../services/api";

export function useResource<T>(load: () => Promise<T>, interval = 5000) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const generation = useRef(0);
  const busy = useRef(false);
  const reload = useCallback(async () => {
    if (busy.current) return;
    busy.current = true;
    const token = generation.current;
    try {
      const result = await load();
      if (token === generation.current) {
        setData(result);
        setError("");
      }
    } catch (e) {
      if (token === generation.current) setError(errorMessage(e));
    } finally {
      if (token === generation.current) {
        busy.current = false;
        setLoading(false);
      }
    }
  }, [load]);
  useEffect(() => {
    generation.current += 1;
    busy.current = false;
    setLoading(true);
    void reload();
    const timer = interval
      ? window.setInterval(() => void reload(), interval)
      : undefined;
    return () => {
      generation.current += 1;
      window.clearInterval(timer);
    };
  }, [reload, interval]);
  return { data, error, loading, reload };
}
