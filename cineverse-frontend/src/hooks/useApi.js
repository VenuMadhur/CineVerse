import { useCallback, useEffect, useState } from 'react';
import { extractErrorMessage } from '../utils/formatters';

/**
 * Generic fetch hook: runs `fetcher` on mount (and whenever `deps`
 * change), exposing { data, loading, error, refetch }. Keeps API
 * calls in service modules and loading/error boilerplate out of pages.
 */
export function useApi(fetcher, deps = [], { enabled = true } = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState(null);

  const refetch = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const result = await fetcher();
      setData(result);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { data, loading, error, refetch, setData };
}
