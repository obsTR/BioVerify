import { useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { EvidenceViewer } from '../components/EvidenceViewer';
import { api } from '../services/api';
import type { EvidenceResponse, AnalysisStatusResponse } from '../types/api';

export function EvidencePage() {
  const { id } = useParams<{ id: string }>();
  const [evidence, setEvidence] = useState<EvidenceResponse | null>(null);
  const [result, setResult] = useState<AnalysisStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) {
      setError('Invalid analysis ID');
      setIsLoading(false);
      return;
    }

    const fetchData = async () => {
      try {
        const [evidenceData, analysisData] = await Promise.all([
          api.getEvidence(id),
          api.getAnalysis(id),
        ]);
        setEvidence(evidenceData);
        setResult(analysisData);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch evidence');
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [id]);

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
          <p className="text-slate-400">Loading evidence...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-5xl mx-auto">
          <div className="bg-red-950/70 border border-red-500/80 rounded-lg p-6">
            <h2 className="text-lg font-semibold text-red-100 mb-2">Error</h2>
            <p className="text-sm text-red-100/90">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!evidence) {
    return (
      <div className="min-h-screen py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-5xl mx-auto">
          <div className="bg-amber-950/60 border border-amber-500/70 rounded-lg p-6">
            <p className="text-sm text-amber-100">No evidence available for this analysis.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-5xl mx-auto">
        <EvidenceViewer evidence={evidence} result={result?.result_json} />
      </div>
    </div>
  );
}
