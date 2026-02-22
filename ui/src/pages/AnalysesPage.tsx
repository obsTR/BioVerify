import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { api } from '../services/api';
import type { AnalysisStatusResponse } from '../types/api';

const verdictColors: Record<string, string> = {
  Human: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
  Synthetic: 'text-red-400 bg-red-500/10 border-red-500/30',
  Inconclusive: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
};

const statusColors: Record<string, string> = {
  queued: 'text-slate-400',
  running: 'text-blue-400',
  done: 'text-emerald-400',
  failed: 'text-red-400',
};

function formatDate(iso?: string): string {
  if (!iso) return '-';
  const d = new Date(iso);
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export function AnalysesPage() {
  const [analyses, setAnalyses] = useState<AnalysisStatusResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listAnalyses(100)
      .then(setAnalyses)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-50">Previous Analyses</h1>
          <p className="text-sm text-slate-400 mt-1">
            {analyses.length} total analysis{analyses.length !== 1 ? 'es' : ''}
          </p>
        </div>
        <Link
          to="/upload"
          className="px-4 py-2 rounded-lg text-sm font-medium bg-emerald-500 text-slate-950 hover:bg-emerald-400 transition-colors shadow-[0_0_18px_rgba(16,185,129,0.5)]"
        >
          New Analysis
        </Link>
      </div>

      {loading && (
        <div className="text-center py-16 text-slate-400">Loading...</div>
      )}

      {error && (
        <div className="bg-red-950/60 border border-red-500/50 rounded-xl p-4 text-red-200 text-sm">
          {error}
        </div>
      )}

      {!loading && !error && analyses.length === 0 && (
        <div className="text-center py-16">
          <p className="text-slate-400 mb-4">No analyses yet.</p>
          <Link
            to="/upload"
            className="text-emerald-400 hover:text-emerald-300 underline"
          >
            Upload your first video
          </Link>
        </div>
      )}

      {!loading && analyses.length > 0 && (
        <div className="bg-slate-950/70 border border-slate-800 rounded-2xl shadow-[0_0_30px_rgba(15,23,42,0.9)] overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wider text-slate-500">
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3">Verdict</th>
                <th className="px-6 py-3">Score</th>
                <th className="px-6 py-3">Confidence</th>
                <th className="px-6 py-3">Created</th>
                <th className="px-6 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {analyses.map((a) => {
                const result = a.result_json;
                const verdict = result?.verdict;
                const linkTarget =
                  a.status === 'done'
                    ? `/analysis/${a.analysis_id}/result`
                    : `/analysis/${a.analysis_id}`;

                return (
                  <tr
                    key={a.analysis_id}
                    className="border-b border-slate-800/50 hover:bg-slate-900/50 transition-colors"
                  >
                    <td className="px-6 py-4">
                      <span className={`text-sm font-medium capitalize ${statusColors[a.status] ?? 'text-slate-400'}`}>
                        {a.status}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      {verdict ? (
                        <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${verdictColors[verdict] ?? ''}`}>
                          {verdict}
                        </span>
                      ) : (
                        <span className="text-xs text-slate-600">-</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-300">
                      {result?.score != null ? `${(result.score * 100).toFixed(1)}%` : '-'}
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-300">
                      {result?.confidence != null ? `${Math.round(result.confidence * 100)}%` : '-'}
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-400">
                      {formatDate(a.created_at)}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <Link
                        to={linkTarget}
                        className="text-xs text-emerald-400 hover:text-emerald-300 underline"
                      >
                        View
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
