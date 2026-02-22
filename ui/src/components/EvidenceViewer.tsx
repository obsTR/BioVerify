import { useState } from 'react';
import { PipelineDiagram } from './PipelineDiagram';
import { LivenessPanel } from './LivenessPanel';
import type { EvidenceResponse, JobResult } from '../types/api';

interface EvidenceViewerProps {
  evidence: EvidenceResponse;
  result?: JobResult;
}

function ImageLightbox({ src, alt, onClose }: { src: string; alt: string; onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-sm cursor-pointer"
      onClick={onClose}
    >
      <button
        onClick={onClose}
        className="absolute top-4 right-4 text-white/70 hover:text-white text-3xl font-light z-50"
        aria-label="Close"
      >
        &times;
      </button>
      <img
        src={src}
        alt={alt}
        className="max-w-[95vw] max-h-[90vh] object-contain rounded-lg shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      />
    </div>
  );
}

export function EvidenceViewer({ evidence, result }: EvidenceViewerProps) {
  const [imageErrors, setImageErrors] = useState<Set<string>>(new Set());
  const [lightboxImage, setLightboxImage] = useState<{ src: string; alt: string } | null>(null);

  const handleImageError = (url: string) => {
    setImageErrors((prev) => new Set(prev).add(url));
  };

  const metrics = result?.metrics_summary || {};

  return (
    <div className="space-y-8">
      {lightboxImage && (
        <ImageLightbox
          src={lightboxImage.src}
          alt={lightboxImage.alt}
          onClose={() => setLightboxImage(null)}
        />
      )}

      <div>
        <h2 className="text-2xl font-bold text-slate-50 mb-2">Evidence & Analysis</h2>
        <p className="text-sm text-slate-400">
          Detailed analysis results including rPPG signals, spectra, and key metrics.
        </p>
      </div>

      {result?.metrics && <PipelineDiagram metrics={result.metrics} />}

      {metrics && Object.keys(metrics).length > 0 && (
        <LivenessPanel metricsSummary={metrics} />
      )}

      {/* Face / ROI visualizations */}
      {evidence.index.artifacts.roi_masks && evidence.index.artifacts.roi_masks.length > 0 && (
        <div className="bg-slate-950/70 border border-slate-800 rounded-2xl shadow-[0_0_30px_rgba(15,23,42,0.9)] p-6">
          <h3 className="text-lg font-semibold text-slate-50 mb-2">Face & ROI Visualizations</h3>
          <p className="text-sm text-slate-400 mb-4">
            Sample frames showing detected face and analysis regions (forehead / cheeks). Click to enlarge.
          </p>
          {(() => {
            const validMasks = evidence.index.artifacts.roi_masks!.filter(
              (maskPath) => evidence.signed_urls[maskPath] && !imageErrors.has(maskPath)
            );
            if (validMasks.length === 0) {
              return (
                <div className="bg-amber-950/60 border border-amber-500/70 rounded-lg p-4">
                  <p className="text-sm text-amber-100">
                    ROI masks found in index but signed URLs not available.
                  </p>
                </div>
              );
            }
            return (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {evidence.index.artifacts.roi_masks!.map((maskPath, idx) => {
                  const signedUrl = evidence.signed_urls[maskPath];
                  if (!signedUrl || imageErrors.has(maskPath)) return null;
                  const alt = `Face / ROI visualization ${idx + 1}`;
                  return (
                    <div
                      key={idx}
                      className="bg-slate-900/70 border border-slate-800 rounded-xl overflow-hidden cursor-pointer group hover:border-emerald-500/40 transition-colors"
                      onClick={() => setLightboxImage({ src: signedUrl, alt })}
                    >
                      <div className="relative">
                        <img
                          src={signedUrl}
                          alt={alt}
                          className="w-full h-full object-cover group-hover:brightness-110 transition-all"
                          onError={() => handleImageError(maskPath)}
                        />
                        <div className="absolute bottom-2 left-2 px-2 py-0.5 rounded-full text-[10px] uppercase tracking-[0.18em] bg-black/60 text-emerald-300 border border-emerald-500/60">
                          ROI Frame {idx + 1}
                        </div>
                        <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity px-2 py-0.5 rounded bg-black/60 text-[10px] text-slate-300">
                          Click to enlarge
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            );
          })()}
        </div>
      )}

      {/* rPPG Traces */}
      {evidence.index.artifacts.rppg_traces && evidence.index.artifacts.rppg_traces.length > 0 && (
        <div className="bg-slate-950/70 border border-slate-800 rounded-2xl shadow-[0_0_30px_rgba(15,23,42,0.9)] p-6">
          <h3 className="text-lg font-semibold text-slate-50 mb-4">rPPG Signal Traces</h3>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {evidence.index.artifacts.rppg_traces.map((tracePath, idx) => {
              const signedUrl = evidence.signed_urls[tracePath];
              if (!signedUrl || imageErrors.has(tracePath)) return null;
              const alt = `rPPG trace ${idx + 1}`;
              return (
                <div
                  key={idx}
                  className="space-y-2 cursor-pointer group"
                  onClick={() => setLightboxImage({ src: signedUrl, alt })}
                >
                  <p className="text-sm font-medium text-slate-200 capitalize">
                    {tracePath.replace(/.*rppg_trace_/, '').replace('.png', '')}
                  </p>
                  <img
                    src={signedUrl}
                    alt={alt}
                    className="w-full border rounded group-hover:border-emerald-500/40 transition-colors"
                    onError={() => handleImageError(tracePath)}
                  />
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* rPPG Spectra */}
      {evidence.index.artifacts.rppg_spectra && evidence.index.artifacts.rppg_spectra.length > 0 && (
        <div className="bg-slate-950/70 border border-slate-800 rounded-2xl shadow-[0_0_30px_rgba(15,23,42,0.9)] p-6">
          <h3 className="text-lg font-semibold text-slate-50 mb-4">Frequency Spectra</h3>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {evidence.index.artifacts.rppg_spectra.map((specPath, idx) => {
              const signedUrl = evidence.signed_urls[specPath];
              if (!signedUrl || imageErrors.has(specPath)) return null;
              const alt = `rPPG spectrum ${idx + 1}`;
              return (
                <div
                  key={idx}
                  className="space-y-2 cursor-pointer group"
                  onClick={() => setLightboxImage({ src: signedUrl, alt })}
                >
                  <p className="text-sm font-medium text-slate-200 capitalize">
                    {specPath.replace(/.*rppg_spectrum_/, '').replace('.png', '')}
                  </p>
                  <img
                    src={signedUrl}
                    alt={alt}
                    className="w-full border rounded group-hover:border-emerald-500/40 transition-colors"
                    onError={() => handleImageError(specPath)}
                  />
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Summary link */}
      {evidence.index.artifacts.summary && (
        <div className="bg-slate-950/70 border border-slate-800 rounded-2xl shadow-[0_0_30px_rgba(15,23,42,0.9)] p-6">
          <h3 className="text-lg font-semibold text-slate-50 mb-4">Summary</h3>
          <p className="text-sm text-slate-400">
            {evidence.signed_urls[evidence.index.artifacts.summary] ? (
              <a
                href={evidence.signed_urls[evidence.index.artifacts.summary]}
                target="_blank"
                rel="noopener noreferrer"
                className="text-emerald-400 hover:underline"
              >
                Download summary.json
              </a>
            ) : (
              <span>Summary: <code className="bg-slate-900/80 px-2 py-1 rounded border border-slate-700">{evidence.index.artifacts.summary}</code></span>
            )}
          </p>
        </div>
      )}

      {Object.keys(evidence.index.artifacts).length === 0 && (
        <div className="bg-amber-950/60 border border-amber-500/60 rounded-lg p-6">
          <p className="text-sm text-amber-100">
            No evidence artifacts available for this analysis.
          </p>
        </div>
      )}
    </div>
  );
}
