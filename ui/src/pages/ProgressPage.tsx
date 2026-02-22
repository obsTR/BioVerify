import { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ProgressTracker } from '../components/ProgressTracker';
import { useAnalysis } from '../hooks/useAnalysis';

export function ProgressPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { status, isLoading, error } = useAnalysis(id || '');

  useEffect(() => {
    if (status?.status === 'done') {
      // Auto-redirect to result page when done
      navigate(`/analysis/${id}/result`, { replace: true });
    }
  }, [status?.status, id, navigate]);

  if (!id) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-300">Invalid analysis ID</p>
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

  if (status?.status === 'failed') {
    return (
      <div className="min-h-screen py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl mx-auto">
          <ProgressTracker analysisId={id} status={status.status} isLoading={isLoading} />
          <div className="mt-6 bg-red-950/70 border border-red-500/80 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-red-100 mb-2">Analysis Failed</h3>
            <p className="text-sm text-red-100/90">
              {status.error_message || 'An error occurred during analysis'}
            </p>
            {status.error_code && (
              <p className="text-xs text-red-600 mt-2">Error Code: {status.error_code}</p>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto">
        <ProgressTracker
          analysisId={id}
          status={status?.status || 'queued'}
          isLoading={isLoading}
        />
      </div>
    </div>
  );
}
