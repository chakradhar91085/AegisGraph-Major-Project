import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';

/**
 * Loads data now and every `intervalMs` after. `error` is a plain-language
 * message; data from the last good load is kept when a refresh fails.
 */
export function usePolling<T>(load: () => Promise<T>, intervalMs: number, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(load, deps);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setData(await run());
      setError(null);
    } catch (err) {
      const status = axios.isAxiosError(err) ? err.response?.status : undefined;
      setError(
        status === 403 ? 'This page is restricted to the Auditor role.'
          : status ? `The server returned an error (HTTP ${status}).`
          : "Can't reach the AegisGraph server.",
      );
    } finally {
      setLoading(false);
    }
  }, [run]);

  useEffect(() => {
    reload();
    const id = setInterval(reload, intervalMs);
    return () => clearInterval(id);
  }, [reload, intervalMs]);

  return { data, error, loading, reload };
}
