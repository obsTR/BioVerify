import type { AnalysisStatus } from '../types/api';

interface StatusBadgeProps {
  status: AnalysisStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const styles = {
    queued: 'bg-slate-900/80 text-slate-200 border-slate-600',
    running: 'bg-sky-900/60 text-sky-200 border-sky-400/70',
    done: 'bg-emerald-900/60 text-emerald-200 border-emerald-400/70',
    failed: 'bg-red-950/70 text-red-200 border-red-500/80',
  };

  const icons = {
    queued: '⏳',
    running: '🔄',
    done: '✅',
    failed: '❌',
  };

  return (
    <span
      className={`inline-flex items-center gap-2 px-3 py-1 rounded-full border text-sm font-medium ${
        styles[status]
      }`}
    >
      <span>{icons[status]}</span>
      <span className="capitalize">{status}</span>
    </span>
  );
}
