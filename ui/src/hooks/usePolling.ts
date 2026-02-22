import { useEffect, useState, useRef } from 'react';

export function usePolling<T>(
  fetchFn: () => Promise<T>,
  interval: number,
  condition: (data: T) => boolean = () => false
): { data: T | null; isLoading: boolean; error: string | null } {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<number | null>(null);
  const shouldStopRef = useRef(false);

  useEffect(() => {
    let isMounted = true;

    const poll = async () => {
      try {
        const result = await fetchFn();
        if (isMounted) {
          setData(result);
          setIsLoading(false);
          setError(null);

          // Stop polling if condition is met
          if (condition(result)) {
            shouldStopRef.current = true;
            if (intervalRef.current) {
              clearInterval(intervalRef.current);
            }
          }
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : 'Polling error');
          setIsLoading(false);
          // Stop polling on error
          shouldStopRef.current = true;
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
          }
        }
      }
    };

    // Initial fetch
    poll();

    // Set up polling if condition not met
    if (!shouldStopRef.current) {
      intervalRef.current = window.setInterval(() => {
        if (!shouldStopRef.current) {
          poll();
        }
      }, interval);
    }

    return () => {
      isMounted = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [fetchFn, interval]);

  return { data, isLoading, error };
}
