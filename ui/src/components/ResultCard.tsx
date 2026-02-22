import { Link } from 'react-router-dom';
import { PipelineDiagram } from './PipelineDiagram';
import { LivenessPanel } from './LivenessPanel';
import type { JobResult } from '../types/api';

interface ResultCardProps {
  result: JobResult;
  analysisId: string;
}

export function ResultCard({ result, analysisId }: ResultCardProps) {
  const verdictColors = {
    Human: 'bg-green-100 text-green-800 border-green-300',
    Synthetic: 'bg-red-100 text-red-800 border-red-300',
    Inconclusive: 'bg-yellow-100 text-yellow-800 border-yellow-300',
  };

  const verdictIcons = {
    Human: '✅',
    Synthetic: '❌',
    Inconclusive: '⚠️',
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-50 mb-4">Analysis Results</h2>

        {result.metrics && (
          <div className="mb-6">
            <PipelineDiagram metrics={result.metrics} />
          </div>
        )}

        {result.metrics_summary && (
          <div className="mb-6">
            <LivenessPanel metricsSummary={result.metrics_summary} />
          </div>
        )}

        <div className="bg-slate-950/70 border border-slate-800 rounded-2xl shadow-[0_0_30px_rgba(15,23,42,0.9)] p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-lg font-semibold text-slate-200 mb-2">Verdict</h3>
              <div
                className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg border text-lg font-bold ${
                  verdictColors[result.verdict]
                }`}
              >
                <span>{verdictIcons[result.verdict]}</span>
                <span>{result.verdict}</span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            <div>
              <h4 className="text-sm font-medium text-slate-400 mb-2">Confidence</h4>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-2xl font-bold text-slate-50">
                    {Math.round(result.confidence * 100)}%
                  </span>
                </div>
                <div className="w-full bg-slate-900 rounded-full h-3">
                  <div
                    className="bg-emerald-500 h-3 rounded-full transition-all duration-500 shadow-[0_0_18px_rgba(16,185,129,0.7)]"
                    style={{ width: `${result.confidence * 100}%` }}
                  ></div>
                </div>
              </div>
            </div>

            <div>
              <h4 className="text-sm font-medium text-slate-400 mb-2">Liveness Score</h4>
              <p className="text-2xl font-bold text-slate-50">{(result.score * 100).toFixed(1)}%</p>
            </div>
          </div>

          {result.reasons && result.reasons.length > 0 && (
            <div className="mb-6">
              <h4 className="text-sm font-medium text-slate-400 mb-2">Reasons</h4>
              <ul className="list-disc list-inside space-y-1 text-sm text-slate-200">
                {result.reasons.map((reason, idx) => (
                  <li key={idx}>{reason}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="pt-4 border-t">
            <Link
              to={`/analysis/${analysisId}/evidence`}
              className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-500 text-slate-950 rounded-lg hover:bg-emerald-400 transition-colors shadow-[0_0_18px_rgba(16,185,129,0.7)]"
            >
              <span>View Evidence</span>
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5l7 7-7 7"
                />
              </svg>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
