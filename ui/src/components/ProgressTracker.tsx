import { StatusBadge } from './StatusBadge';
import type { AnalysisStatus } from '../types/api';

interface ProgressTrackerProps {
  analysisId: string;
  status: AnalysisStatus;
  isLoading?: boolean;
}

export function ProgressTracker({ analysisId, status, isLoading }: ProgressTrackerProps) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-50 mb-2">Analysis Progress</h2>
        <p className="text-sm text-slate-400">
          Analysis ID:{' '}
          <code className="bg-slate-900/80 px-2 py-1 rounded border border-slate-700">
            {analysisId}
          </code>
        </p>
      </div>

      <div className="flex items-center gap-4">
        <StatusBadge status={status} />
        {isLoading && status !== 'done' && status !== 'failed' && (
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-emerald-500"></div>
            <span>Processing...</span>
          </div>
        )}
      </div>

      {status === 'running' && (
        <div className="bg-sky-950/60 border border-sky-500/70 rounded-lg p-4">
          <p className="text-sm text-sky-100">
            Your video is being analyzed. This may take a few moments...
          </p>
        </div>
      )}

      {status === 'queued' && (
        <div className="bg-slate-900/70 border border-slate-700 rounded-lg p-4">
          <p className="text-sm text-slate-200">
            Your analysis is queued and will start processing shortly...
          </p>
        </div>
      )}
    </div>
  );
}
