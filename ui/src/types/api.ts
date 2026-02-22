export type AnalysisStatus = 'queued' | 'running' | 'done' | 'failed';

export interface UploadResponse {
  analysis_id: string;
  status: AnalysisStatus;
}

export interface AnalysisStatusResponse {
  analysis_id: string;
  status: AnalysisStatus;
  policy_name?: string;
  result_json?: JobResult;
  error_code?: string;
  error_message?: string;
  created_at?: string;
  started_at?: string;
  finished_at?: string;
}

/** Pipeline diagnostics: where the video passed or failed (for troubleshooting). */
export interface PipelineMetrics {
  ingest?: { num_windows?: number };
  face?: { windows?: unknown[] };
  roi?: {
    total_frames?: number;
    frames_with_all_regions_valid?: number;
    frames_per_region?: Record<string, number>;
  };
  rppg?: {
    samples_per_region?: Record<string, number>;
    duration_seconds?: number;
  };
}

/** Individual liveness feature used in scoring. */
export interface LivenessFeatureDetail {
  value: number;
  weight: number;
}

/** Scoring breakdown returned by the engine. */
export interface ScoringBreakdown {
  liveness_score?: number;
  base_score?: number;
  gate_factor?: number;
  aggregate_sqi?: number;
  tau_auth?: number;
  features?: Record<string, LivenessFeatureDetail>;
  gates?: Record<string, { value: number; threshold: number; gate: number }>;
  // Legacy fields (pre-liveness upgrade)
  presence?: number;
  consistency?: number;
  score?: number;
}

/** Liveness features computed from rPPG signals. */
export interface LivenessFeatures {
  hr_plausibility: number;
  spectral_concentration: number;
  spectral_sharpness: number;
  inter_region_coherence: number;
  phase_coherence: number;
  periodicity: number;
  harmonic_structure: number;
  hrv_score: number;
  hrv_sdnn_ms: number;
  temporal_hr_stability: number;
  respiratory_score: number;
}

export interface MetricsSummary {
  sqi?: {
    aggregate?: number;
    regions?: Record<string, number>;
    motion_penalty?: number;
    tau_sqi?: number;
  };
  features?: {
    regions?: Record<string, any>;
    stability?: number;
    liveness?: LivenessFeatures;
  };
  scoring?: ScoringBreakdown;
}

export interface JobResult {
  verdict: 'Human' | 'Synthetic' | 'Inconclusive';
  score: number;
  confidence: number;
  reasons: string[];
  metrics_summary?: MetricsSummary;
  metrics?: PipelineMetrics;
  evidence_index?: string;
  engine_version?: string;
  policy_version?: string;
}

export interface EvidenceIndex {
  config_version: string;
  artifacts: {
    summary?: string;
    rppg_traces?: string[];
    rppg_spectra?: string[];
    roi_masks?: string[];
    [key: string]: any;
  };
}

export interface EvidenceResponse {
  index: EvidenceIndex;
  signed_urls: Record<string, string>;
}

export interface HealthResponse {
  status: 'ok';
  engine_version?: string;
  policy_versions?: string[];
}
