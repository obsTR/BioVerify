import type { PipelineMetrics } from '../types/api';

type StageStatus = 'ok' | 'warning' | 'fail';

interface Stage {
  id: string;
  label: string;
  status: StageStatus;
  summary: string;
  detail?: React.ReactNode;
}

interface PipelineDiagramProps {
  metrics: PipelineMetrics;
  className?: string;
}

function getIngestStage(m: PipelineMetrics): Stage {
  const n = m.ingest?.num_windows ?? 0;
  const status: StageStatus = n >= 1 ? 'ok' : 'fail';
  return {
    id: 'ingest',
    label: 'Ingest',
    status,
    summary: `${n} window${n !== 1 ? 's' : ''}`,
  };
}

function getFaceStage(m: PipelineMetrics): Stage {
  const windows = m.face?.windows ?? [];
  const n = Array.isArray(windows) ? windows.length : 0;
  const status: StageStatus = n >= 1 ? 'ok' : 'fail';
  return {
    id: 'face',
    label: 'Face',
    status,
    summary: `${n} window${n !== 1 ? 's' : ''} with face`,
  };
}

function getRoiStage(m: PipelineMetrics): Stage {
  const roi = m.roi ?? {};
  const total = roi.total_frames ?? 0;
  const allValid = roi.frames_with_all_regions_valid ?? 0;
  const perRegion = roi.frames_per_region ?? {};
  let status: StageStatus = 'fail';
  if (total === 0) status = 'fail';
  else if (allValid > 0) status = 'ok';
  else status = 'warning';

  const detail = (
    <div className="mt-2 text-xs space-y-1">
      <div>{total} total frames, {allValid} with all regions valid</div>
      {Object.keys(perRegion).length > 0 && (
        <div className="flex flex-wrap gap-x-3 gap-y-0.5">
          {Object.entries(perRegion).map(([name, count]) => (
            <span
              key={name}
              className={count === 0 ? 'text-red-600 font-medium' : 'text-gray-600'}
              title={count === 0 ? 'No frames had this region valid' : undefined}
            >
              {name.replace('_', ' ')}: {count}
            </span>
          ))}
        </div>
      )}
    </div>
  );

  return {
    id: 'roi',
    label: 'ROI',
    status,
    summary: `${allValid} / ${total} frames`,
    detail,
  };
}

function getRppgStage(m: PipelineMetrics): Stage {
  const rppg = m.rppg ?? {};
  const duration = rppg.duration_seconds ?? 0;
  const samples = rppg.samples_per_region ?? {};
  const totalSamples = Object.values(samples).reduce((a, b) => a + (b ?? 0), 0);
  let status: StageStatus = 'fail';
  if (duration > 0 && totalSamples > 0) status = 'ok';
  else if (duration === 0 && totalSamples === 0) status = 'warning';

  const summary = duration > 0
    ? `${duration.toFixed(1)}s signal`
    : 'No signal (blocked by ROI)';

  return {
    id: 'rppg',
    label: 'rPPG',
    status,
    summary,
    detail: totalSamples > 0 ? (
      <div className="mt-2 text-xs text-gray-600">
        Samples: {Object.entries(samples).map(([k, v]) => `${k.replace('_', ' ')}: ${v}`).join(', ')}
      </div>
    ) : undefined,
  };
}

const statusStyles: Record<StageStatus, string> = {
  ok: 'border-emerald-500 bg-emerald-50/80',
  warning: 'border-amber-500 bg-amber-50/80',
  fail: 'border-red-400 bg-red-50/80',
};

const statusLabel: Record<StageStatus, string> = {
  ok: 'OK',
  warning: 'Issue',
  fail: 'Failed',
};

export function PipelineDiagram({ metrics, className = '' }: PipelineDiagramProps) {
  const stages: Stage[] = [
    getIngestStage(metrics),
    getFaceStage(metrics),
    getRoiStage(metrics),
    getRppgStage(metrics),
  ];

  return (
    <div className={`bg-slate-950/70 border border-slate-800 rounded-2xl shadow-[0_0_30px_rgba(15,23,42,0.9)] p-6 ${className}`}>
      <h3 className="text-lg font-semibold text-slate-50 mb-2">Pipeline</h3>
      <p className="text-sm text-slate-400 mb-4">
        Where the video passed or failed. Use this to tune detection (e.g. ROI coverage threshold, face size).
      </p>
      <div className="flex flex-wrap items-stretch gap-0 min-w-0">
        {stages.map((stage, i) => (
          <div key={stage.id} className="flex items-stretch min-w-0 flex-1 basis-0">
            {i > 0 && (
              <div className="flex items-center px-1 shrink-0">
                <svg className="w-6 h-6 text-gray-300" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41z" />
                </svg>
              </div>
            )}
            <div
              className={`flex-1 min-w-0 rounded-lg border-2 p-3 ${statusStyles[stage.status]}`}
              title={stage.detail ? undefined : statusLabel[stage.status]}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-gray-900 truncate">{stage.label}</span>
                <span
                  className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded ${
                    stage.status === 'ok'
                      ? 'text-emerald-700 bg-emerald-100'
                      : stage.status === 'warning'
                      ? 'text-amber-700 bg-amber-100'
                      : 'text-red-700 bg-red-100'
                  }`}
                >
                  {statusLabel[stage.status]}
                </span>
              </div>
              <p className="text-sm text-gray-700 mt-1 truncate">{stage.summary}</p>
              {stage.detail}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
