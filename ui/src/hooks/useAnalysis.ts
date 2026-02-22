import { useEffect, useState } from 'react';
import { api } from '../services/api';
import type { AnalysisStatusResponse } from '../types/api';

export function useAnalysis(analysisId: string) {
  const [status, setStatus] = useState<AnalysisStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    let intervalId: number | null = null;

    const fetchStatus = async () => {
      try {
        const result = await api.getAnalysis(analysisId);
        if (isMounted) {
          setStatus(result);
          setIsLoading(false);
          setError(null);

          // Stop polling if done or failed
          if (result.status === 'done' || result.status === 'failed') {
            if (intervalId) {
              clearInterval(intervalId);
            }
          }
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : 'Failed to fetch analysis');
          setIsLoading(false);
          if (intervalId) {
            clearInterval(intervalId);
          }
        }
      }
    };

    // Initial fetch
    fetchStatus();

    // Poll every 2 seconds if not done/failed
    intervalId = window.setInterval(() => {
      if (isMounted && status && status.status !== 'done' && status.status !== 'failed') {
        fetchStatus();
      }
    }, 2000);

    return () => {
      isMounted = false;
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [analysisId]);

  return { status, isLoading, error };
}
