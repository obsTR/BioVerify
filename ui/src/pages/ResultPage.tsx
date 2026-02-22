import { useParams, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { ResultCard } from '../components/ResultCard';
import { api } from '../services/api';
import type { AnalysisStatusResponse } from '../types/api';

export function ResultPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [analysis, setAnalysis] = useState<AnalysisStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) {
      setError('Invalid analysis ID');
      setIsLoading(false);
      return;
    }

    const fetchAnalysis = async () => {
      try {
        const result = await api.getAnalysis(id);
        setAnalysis(result);
        if (result.status !== 'done') {
          // Redirect to progress page if not done
          navigate(`/analysis/${id}`, { replace: true });
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch results');
      } finally {
        setIsLoading(false);
      }
    };

    fetchAnalysis();
  }, [id, navigate]);

  if (!id) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-300">Invalid analysis ID</p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-emerald-500 mx-auto mb-4"></div>
          <p className="text-slate-400">Loading results...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl mx-auto">
          <div className="bg-red-950/70 border border-red-500/80 rounded-lg p-6">
            <h2 className="text-lg font-semibold text-red-100 mb-2">Error</h2>
            <p className="text-sm text-red-100/90">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!analysis || !analysis.result_json) {
    return (
      <div className="min-h-screen py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl mx-auto">
          <div className="bg-amber-950/60 border border-amber-500/70 rounded-lg p-6">
            <p className="text-sm text-amber-100">No results available for this analysis.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto">
        <ResultCard result={analysis.result_json} analysisId={id} />
      </div>
    </div>
  );
}
