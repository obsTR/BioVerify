import type { MetricsSummary } from '../types/api';

interface LivenessPanelProps {
  metricsSummary: MetricsSummary;
  className?: string;
}

interface FeatureBar {
  label: string;
  description: string;
  value: number;
  weight: number;
}

function getFeatureBars(metricsSummary: MetricsSummary): FeatureBar[] {
  const scoring = metricsSummary.scoring;
  const features = scoring?.features;
  if (!features) return [];

  const labels: Record<string, { label: string; description: string }> = {
    hr_plausibility: {
      label: 'Heart Rate Plausibility',
      description: 'Is there a clear heartbeat peak above the noise floor (SNR > 6)? GATE',
    },
    spectral_concentration: {
      label: 'Spectral Concentration',
      description: 'Is rPPG power concentrated in a narrow band (real pulse) or diffuse (noise)? GATE',
    },
    spectral_sharpness: {
      label: 'Spectral Sharpness (Q Factor)',
      description: 'How narrow is the heart rate peak? Real PPG: Q > 8 (sharp). Noise: Q < 4 (broad). GATE',
    },
    inter_region_coherence: {
      label: 'Inter-Region Coherence',
      description: 'Are forehead and cheek signals correlated? Real faces share one heartbeat.',
    },
    phase_coherence: {
      label: 'Pulse Transit Time',
      description: 'Do pulse signals show consistent propagation delay between face regions? Real faces have arterial wave transit; deepfakes do not.',
    },
    periodicity: {
      label: 'Signal Periodicity',
      description: 'Does the signal show repeating beat-to-beat pattern confirmed by 2nd autocorrelation peak?',
    },
    harmonic_structure: {
      label: 'Harmonic Structure',
      description: 'Does the spectrum show a 2nd harmonic at 2x heart rate? Real PPG has this; noise does not.',
    },
    hrv: {
      label: 'Heart Rate Variability',
      description: 'Does beat-to-beat interval variation match normal physiology (20-120 ms SDNN)?',
    },
    temporal_stability: {
      label: 'Temporal HR Stability',
      description: 'Is heart rate consistent across time windows? GATE — erratic HR = noise.',
    },
    respiratory: {
      label: 'Respiratory Modulation',
      description: 'Is there a clear respiratory peak modulating pulse amplitude?',
    },
  };

  return Object.entries(features).map(([key, detail]) => ({
    label: labels[key]?.label ?? key,
    description: labels[key]?.description ?? '',
    value: detail.value,
    weight: detail.weight,
  }));
}

function barColor(value: number): string {
  if (value >= 0.7) return 'bg-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.5)]';
  if (value >= 0.4) return 'bg-amber-500 shadow-[0_0_12px_rgba(245,158,11,0.5)]';
  return 'bg-red-500 shadow-[0_0_12px_rgba(239,68,68,0.5)]';
}

function valueLabel(value: number): string {
  if (value >= 0.7) return 'Strong';
  if (value >= 0.4) return 'Moderate';
  if (value > 0) return 'Weak';
  return 'None';
}

export function LivenessPanel({ metricsSummary, className = '' }: LivenessPanelProps) {
  const bars = getFeatureBars(metricsSummary);
  const liveness = metricsSummary.features?.liveness;
  const scoring = metricsSummary.scoring;
  const sqi = metricsSummary.sqi;

  if (bars.length === 0 && !liveness) return null;

  const livenessScore = scoring?.liveness_score;
  const threshold = scoring?.tau_auth;

  return (
    <div className={`bg-slate-950/70 border border-slate-800 rounded-2xl shadow-[0_0_30px_rgba(15,23,42,0.9)] p-6 ${className}`}>
      <h3 className="text-lg font-semibold text-slate-50 mb-1">Liveness Analysis</h3>
      <p className="text-sm text-slate-400 mb-5">
        Physiological features extracted from the rPPG signal. Real humans produce distinctive patterns that deepfakes cannot replicate.
      </p>

      {/* Overall liveness score */}
      {livenessScore !== undefined && (
        <div className="mb-6 p-4 rounded-xl bg-slate-900/80 border border-slate-700">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-slate-300">Liveness Score</span>
            <span className="text-2xl font-bold text-slate-50">{(livenessScore * 100).toFixed(1)}%</span>
          </div>
          <div className="relative w-full h-4 bg-slate-800 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ${
                livenessScore >= (threshold ?? 0.45) ? 'bg-emerald-500' : 'bg-red-500'
              }`}
              style={{ width: `${Math.min(100, livenessScore * 100)}%` }}
            />
            {threshold !== undefined && (
              <div
                className="absolute top-0 bottom-0 w-0.5 bg-slate-300"
                style={{ left: `${threshold * 100}%` }}
                title={`Threshold: ${(threshold * 100).toFixed(0)}%`}
              />
            )}
          </div>
          <div className="flex justify-between mt-1 text-xs text-slate-500">
            <span>Synthetic</span>
            {threshold !== undefined && (
              <span className="text-slate-400">Threshold: {(threshold * 100).toFixed(0)}%</span>
            )}
            <span>Human</span>
          </div>
          {/* Gate factor info */}
          {scoring?.gate_factor !== undefined && scoring.gate_factor < 1.0 && (
            <div className="mt-3 p-2 rounded-lg bg-red-950/50 border border-red-500/30">
              <p className="text-xs text-red-300">
                Score penalized by critical gates (factor: {(scoring.gate_factor * 100).toFixed(0)}%).
                {scoring.base_score !== undefined && (
                  <> Base score: {(scoring.base_score * 100).toFixed(1)}% &rarr; Gated: {(livenessScore * 100).toFixed(1)}%</>
                )}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Key metrics */}
      {liveness && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <div className="bg-slate-900/60 rounded-lg p-3 border border-slate-700/50">
            <div className="text-xs text-slate-400 mb-1">Heart Rate</div>
            <div className="text-lg font-bold text-slate-50">
              {liveness.hr_plausibility >= 1 ? 'Valid' : 'Invalid'}
            </div>
          </div>
          <div className="bg-slate-900/60 rounded-lg p-3 border border-slate-700/50">
            <div className="text-xs text-slate-400 mb-1">HRV (SDNN)</div>
            <div className="text-lg font-bold text-slate-50">
              {liveness.hrv_sdnn_ms > 0 ? `${liveness.hrv_sdnn_ms.toFixed(0)} ms` : 'N/A'}
            </div>
          </div>
          <div className="bg-slate-900/60 rounded-lg p-3 border border-slate-700/50">
            <div className="text-xs text-slate-400 mb-1">Coherence</div>
            <div className="text-lg font-bold text-slate-50">
              {(liveness.inter_region_coherence * 100).toFixed(0)}%
            </div>
          </div>
          <div className="bg-slate-900/60 rounded-lg p-3 border border-slate-700/50">
            <div className="text-xs text-slate-400 mb-1">Signal Quality</div>
            <div className="text-lg font-bold text-slate-50">
              {sqi?.aggregate !== undefined ? (sqi.aggregate * 100).toFixed(0) + '%' : 'N/A'}
            </div>
          </div>
        </div>
      )}

      {/* Feature breakdown bars */}
      {bars.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-slate-300 mb-2">Feature Breakdown</h4>
          {bars.map((bar) => (
            <div key={bar.label} className="group">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm text-slate-300" title={bar.description}>
                  {bar.label}
                  <span className="text-xs text-slate-600 ml-2">
                    (w={bar.weight.toFixed(2)})
                  </span>
                </span>
                <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                  bar.value >= 0.7
                    ? 'text-emerald-400 bg-emerald-500/10'
                    : bar.value >= 0.4
                    ? 'text-amber-400 bg-amber-500/10'
                    : 'text-red-400 bg-red-500/10'
                }`}>
                  {(bar.value * 100).toFixed(0)}% — {valueLabel(bar.value)}
                </span>
              </div>
              <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${barColor(bar.value)}`}
                  style={{ width: `${Math.min(100, bar.value * 100)}%` }}
                />
              </div>
              <p className="text-xs text-slate-600 mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                {bar.description}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
