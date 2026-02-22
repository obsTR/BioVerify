from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np
from scipy import signal as sp_signal

from .utils.logging import get_logger

logger = get_logger(__name__)


# ── Physiological constants ──────────────────────────────────────────

HR_MIN_HZ = 0.67   # 40 BPM
HR_MAX_HZ = 3.0    # 180 BPM
RESP_LOW_HZ = 0.15
RESP_HIGH_HZ = 0.4

MIN_PEAK_SNR = 4.0


def _find_dominant_frequency(
    filt: np.ndarray, fs: float
) -> Tuple[float, np.ndarray, np.ndarray, float]:
    """
    Return (f0_hz, freqs, power, peak_snr).
    f0_hz is 0 if no clear peak above noise floor.
    """
    win = np.hanning(len(filt))
    x_win = filt * win
    freqs = np.fft.rfftfreq(len(x_win), d=1.0 / fs)
    power = np.abs(np.fft.rfft(x_win)) ** 2
    if power.size == 0:
        return 0.0, freqs, power, 0.0

    mask = (freqs >= HR_MIN_HZ) & (freqs <= HR_MAX_HZ)
    if not mask.any():
        return 0.0, freqs, power, 0.0

    band_power = power[mask]
    peak_val = float(band_power.max())
    median_val = float(np.median(band_power))
    peak_snr = peak_val / max(median_val, 1e-12)

    if peak_snr < MIN_PEAK_SNR:
        return 0.0, freqs, power, peak_snr

    idx_in_band = np.where(mask)[0]
    best = idx_in_band[band_power.argmax()]
    f0 = float(freqs[best])

    return f0, freqs, power, peak_snr


def _spectral_q_factor(
    freqs: np.ndarray, power: np.ndarray, f0_hz: float
) -> float:
    """
    Q factor (sharpness) of the spectral peak at f0.
    Q = f0 / bandwidth_at_half_max.
    Real PPG: Q > 8 (very narrow peak).
    Noise/deepfake: Q < 4 (broad or multi-peak).
    Returns score in [0, 1].
    """
    if f0_hz <= 0 or power.size == 0:
        return 0.0

    mask = (freqs >= HR_MIN_HZ) & (freqs <= HR_MAX_HZ)
    if not mask.any():
        return 0.0

    band_freqs = freqs[mask]
    band_power = power[mask]
    peak_val = float(band_power.max())
    half_max = peak_val / 2.0

    above_half = band_power >= half_max
    if not above_half.any():
        return 0.0

    indices = np.where(above_half)[0]
    bw_bins = indices[-1] - indices[0] + 1
    if bw_bins == 0:
        return 0.0

    freq_res = float(band_freqs[1] - band_freqs[0]) if len(band_freqs) > 1 else 1.0
    bandwidth = bw_bins * freq_res
    if bandwidth < 1e-6:
        return 1.0

    q = f0_hz / bandwidth
    # Q 8-20 = real PPG (score 0.8-1.0), Q 4-8 = borderline (0.3-0.8), Q < 4 = noise (0-0.3)
    if q >= 5:
        return float(np.clip(0.8 + 0.2 * min((q - 5) / 10.0, 1.0), 0.8, 1.0))
    elif q >= 2:
        return float(0.3 + 0.5 * (q - 2) / 3.0)
    else:
        return float(np.clip(q / 2.0 * 0.3, 0.0, 0.3))


def _phase_coherence(
    filtered_signals: Dict[str, np.ndarray], fs: float, f0_hz: float
) -> float:
    """
    Check if pulse signals have consistent phase relationships between
    face regions. In real faces, the pulse wave propagates from forehead
    to cheeks with a small time delay (5-30ms). This phase relationship
    is consistent across the recording.

    Deepfakes have random or zero phase delay because there's no
    arterial wave propagation.

    At typical video frame rates (30fps), pulse transit time is sub-sample
    (5-30ms vs 33ms/frame). Signals are upsampled to >=200Hz for
    sufficient temporal resolution.

    Returns score in [0, 1].
    """
    names = list(filtered_signals.keys())
    if len(names) < 2 or f0_hz <= 0:
        return 0.0

    target_fs = 200.0
    upsample_factor = max(1, int(np.ceil(target_fs / fs)))
    effective_fs = fs * upsample_factor

    min_delay_samples = max(1, int(0.005 * effective_fs))
    max_delay_samples = int(0.050 * effective_fs)

    phase_scores = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a = filtered_signals[names[i]]
            b = filtered_signals[names[j]]
            if len(a) < 10 or len(b) < 10:
                continue
            n = min(len(a), len(b))
            a, b = a[:n], b[:n]

            if upsample_factor > 1:
                t_orig = np.arange(n)
                t_up = np.linspace(0, n - 1, n * upsample_factor)
                a = np.interp(t_up, t_orig, a)
                b = np.interp(t_up, t_orig, b)
                n = len(a)

            cc = np.correlate(a - a.mean(), b - b.mean(), mode="full")
            denom = np.sqrt(np.sum((a - a.mean())**2) * np.sum((b - b.mean())**2))
            if denom < 1e-10:
                phase_scores.append(0.0)
                continue
            cc = cc / denom

            center = len(cc) // 2
            search_range = slice(
                max(0, center - max_delay_samples),
                min(len(cc), center + max_delay_samples + 1)
            )
            cc_segment = cc[search_range]
            if len(cc_segment) == 0:
                phase_scores.append(0.0)
                continue

            peak_idx_local = np.argmax(np.abs(cc_segment))
            peak_lag = peak_idx_local - (center - max(0, center - max_delay_samples))
            peak_corr = float(np.abs(cc_segment[peak_idx_local]))
            abs_lag = abs(peak_lag)

            if abs_lag < min_delay_samples:
                delay_score = 0.3
            elif min_delay_samples <= abs_lag <= max_delay_samples:
                delay_score = 1.0
            else:
                delay_score = 0.2

            win_samples = int(2.0 * effective_fs)
            step = max(1, win_samples // 2)
            delays = []
            for start in range(0, n - win_samples + 1, step):
                seg_a = a[start:start + win_samples]
                seg_b = b[start:start + win_samples]
                seg_cc = np.correlate(seg_a - seg_a.mean(), seg_b - seg_b.mean(), mode="full")
                seg_center = len(seg_cc) // 2
                seg_range = slice(
                    max(0, seg_center - max_delay_samples),
                    min(len(seg_cc), seg_center + max_delay_samples + 1)
                )
                seg_cc_seg = seg_cc[seg_range]
                if len(seg_cc_seg) > 0:
                    delays.append(int(np.argmax(np.abs(seg_cc_seg))))

            if len(delays) >= 3:
                delay_std = float(np.std(delays))
                max_acceptable_std = 3.0 * upsample_factor
                consistency = float(np.clip(1.0 - delay_std / max_acceptable_std, 0.0, 1.0))
            else:
                consistency = 0.3

            score = peak_corr * delay_score * consistency
            phase_scores.append(float(np.clip(score, 0.0, 1.0)))

    if not phase_scores:
        return 0.0
    return float(np.clip(np.mean(phase_scores), 0.0, 1.0))


def _periodicity(filt: np.ndarray, fs: float, f0_hz: float) -> float:
    """
    Periodicity via autocorrelation at expected pulse period.
    Requires 2nd autocorrelation peak at 2x lag for confirmation.
    """
    ac = np.correlate(filt - filt.mean(), filt - filt.mean(), mode="full")
    ac = ac[len(ac) // 2:]
    if ac.size <= 1 or ac[0] < 1e-10:
        return 0.0
    ac_norm = ac / ac[0]

    if f0_hz > 0:
        expected_lag = int(fs / f0_hz)
        search_start = max(1, expected_lag - int(0.15 * expected_lag))
        search_end = min(len(ac_norm), expected_lag + int(0.15 * expected_lag) + 1)
        if search_start < search_end:
            peak_val = float(ac_norm[search_start:search_end].max())
            lag2_start = max(1, 2 * expected_lag - int(0.15 * expected_lag))
            lag2_end = min(len(ac_norm), 2 * expected_lag + int(0.15 * expected_lag) + 1)
            if lag2_start < lag2_end and lag2_end <= len(ac_norm):
                second_peak = float(ac_norm[lag2_start:lag2_end].max())
                return float(np.clip((peak_val + second_peak) / 2.0, 0.0, 1.0))
            return float(np.clip(peak_val * 0.7, 0.0, 1.0))

    return float(np.clip(ac_norm[1:].max() * 0.5, 0.0, 1.0))


def _harmonic_ratio(freqs: np.ndarray, power: np.ndarray, f0: float) -> float:
    if power.size == 0 or f0 <= 0:
        return 0.0
    f2 = 2.0 * f0
    idx_f0 = int(np.argmin(np.abs(freqs - f0)))
    idx_f2 = int(np.argmin(np.abs(freqs - f2)))
    p_f0 = float(power[idx_f0])
    p_f2 = float(power[idx_f2]) if idx_f2 < len(power) else 0.0
    return float(p_f2 / max(p_f0, 1e-6))


def _harmonic_score(freqs: np.ndarray, power: np.ndarray, f0: float) -> float:
    """
    Real PPG has 2nd harmonic at 2*f0 with 10-50% of fundamental power.
    """
    ratio = _harmonic_ratio(freqs, power, f0)
    if ratio <= 0.005:
        return 0.0
    if 0.03 <= ratio <= 0.80:
        return 1.0
    if ratio < 0.03:
        return float(ratio / 0.03)
    return float(np.clip(1.0 - (ratio - 0.80) / 0.4, 0.0, 1.0))


def _hr_plausibility(f0_hz: float, peak_snr: float) -> float:
    if f0_hz <= 0 or not (HR_MIN_HZ <= f0_hz <= HR_MAX_HZ):
        return 0.0
    snr_score = float(np.clip((peak_snr - MIN_PEAK_SNR) / 8.0, 0.0, 1.0))
    return 0.4 + 0.6 * snr_score


def _spectral_concentration(
    freqs: np.ndarray, power: np.ndarray, f0_hz: float, bandwidth_hz: float = 0.30
) -> float:
    if power.size == 0 or f0_hz <= 0:
        return 0.0
    hr_mask = (freqs >= HR_MIN_HZ) & (freqs <= HR_MAX_HZ)
    total = float(power[hr_mask].sum()) if hr_mask.any() else float(power.sum())
    if total < 1e-12:
        return 0.0
    band_mask = (freqs >= f0_hz - bandwidth_hz) & (freqs <= f0_hz + bandwidth_hz)
    band_power = float(power[band_mask].sum()) if band_mask.any() else 0.0
    return float(np.clip(band_power / total, 0.0, 1.0))


def _inter_region_coherence(filtered_signals: Dict[str, np.ndarray]) -> float:
    names = list(filtered_signals.keys())
    if len(names) < 2:
        return 0.0

    correlations = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a = filtered_signals[names[i]]
            b = filtered_signals[names[j]]
            if len(a) < 4 or len(b) < 4:
                continue
            n = min(len(a), len(b))
            a, b = a[:n], b[:n]
            if np.std(a) < 1e-10 or np.std(b) < 1e-10:
                correlations.append(0.0)
                continue
            r = float(np.corrcoef(a, b)[0, 1])
            correlations.append(max(0.0, r))

    if not correlations:
        return 0.0
    return float(np.clip(np.mean(correlations), 0.0, 1.0))


def _hrv_proxy(filt: np.ndarray, fs: float, f0_hz: float) -> Tuple[float, float]:
    if len(filt) < 10 or f0_hz <= 0:
        return 0.0, 0.0

    min_dist = max(1, int(0.5 * fs / f0_hz))
    sig_std = np.std(filt)
    if sig_std < 1e-10:
        return 0.0, 0.0

    peaks, _ = sp_signal.find_peaks(filt, distance=min_dist, prominence=0.3 * sig_std)
    if len(peaks) < 5:
        return 0.0, 0.0

    ipi = np.diff(peaks) / fs * 1000.0
    sdnn = float(np.std(ipi))
    mean_ipi = float(np.mean(ipi))
    expected_ipi = 1000.0 / f0_hz if f0_hz > 0 else 0.0

    if expected_ipi > 0 and abs(mean_ipi - expected_ipi) > 0.4 * expected_ipi:
        return sdnn, 0.1

    if 20 <= sdnn <= 120:
        hrv_score = 1.0
    elif sdnn < 5:
        hrv_score = 0.15
    elif sdnn > 300:
        hrv_score = 0.1
    elif sdnn < 20:
        hrv_score = float(np.clip(sdnn / 20.0, 0.1, 1.0))
    else:
        hrv_score = float(np.clip(1.0 - (sdnn - 120) / 300.0, 0.1, 1.0))

    return sdnn, hrv_score


def _temporal_hr_stability(filt: np.ndarray, fs: float, window_sec: float = 4.0) -> float:
    win_samples = int(window_sec * fs)
    if len(filt) < win_samples * 2:
        return 0.3

    step = max(1, win_samples // 2)
    hr_estimates: List[float] = []
    local_snr_threshold = 3.0

    for start in range(0, len(filt) - win_samples + 1, step):
        chunk = filt[start:start + win_samples]
        win = np.hanning(len(chunk))
        freqs = np.fft.rfftfreq(len(chunk), d=1.0 / fs)
        power = np.abs(np.fft.rfft(chunk * win)) ** 2
        mask = (freqs >= HR_MIN_HZ) & (freqs <= HR_MAX_HZ)
        if not mask.any():
            continue
        band_power = power[mask]
        peak_val = float(band_power.max())
        median_val = float(np.median(band_power))
        if median_val > 0 and peak_val / median_val >= local_snr_threshold:
            idx_in_band = np.where(mask)[0]
            best = idx_in_band[band_power.argmax()]
            hr_estimates.append(float(freqs[best] * 60))

    if len(hr_estimates) < 2:
        return 0.1

    hr_std = float(np.std(hr_estimates))

    if 0.5 <= hr_std <= 10.0:
        return 1.0
    elif hr_std < 0.1:
        return 0.3
    elif hr_std > 30:
        return 0.1
    elif hr_std < 0.5:
        return float(np.clip(hr_std / 0.5, 0.3, 1.0))
    else:
        return float(np.clip(1.0 - (hr_std - 10.0) / 30.0, 0.1, 1.0))


def _respiratory_modulation(filt: np.ndarray, fs: float) -> float:
    if len(filt) < int(fs * 5):
        return 0.3

    analytic = sp_signal.hilbert(filt)
    envelope = np.abs(analytic)

    if np.std(envelope) < 1e-10:
        return 0.0

    freqs = np.fft.rfftfreq(len(envelope), d=1.0 / fs)
    power = np.abs(np.fft.rfft(envelope - envelope.mean())) ** 2
    total = float(power.sum())
    if total < 1e-12:
        return 0.0

    resp_mask = (freqs >= RESP_LOW_HZ) & (freqs <= RESP_HIGH_HZ)
    if not resp_mask.any():
        return 0.0

    resp_power = power[resp_mask]
    resp_peak = float(resp_power.max())
    resp_median = float(np.median(resp_power))

    resp_snr = resp_peak / max(resp_median, 1e-12)
    if resp_snr < 3.0:
        return 0.1

    band_ratio = float(resp_power.sum()) / total
    return float(np.clip(band_ratio * 3.0, 0.0, 1.0))


# ── Main entry point ─────────────────────────────────────────────────

def compute_features(rppg_metrics: Dict[str, Any]) -> Dict[str, Any]:
    fs = float(rppg_metrics["sampling_rate"])
    regions = rppg_metrics["regions"]
    feat_per_region: Dict[str, Any] = {}
    filtered_signals: Dict[str, np.ndarray] = {}

    for name, data in regions.items():
        filt = np.asarray(data.get("filtered", []), dtype=float)
        if filt.size < 4:
            feat_per_region[name] = {
                "f0_hz": 0.0, "hr_bpm": 0.0, "peak_snr": 0.0,
                "periodicity": 0.0, "harmonic_ratio": 0.0,
                "harmonic_score": 0.0, "spectral_concentration": 0.0,
                "spectral_q": 0.0, "hr_plausible": 0.0,
            }
            continue

        filtered_signals[name] = filt
        f0, freqs, power, peak_snr = _find_dominant_frequency(filt, fs)
        hr = float(60.0 * f0)

        feat_per_region[name] = {
            "f0_hz": f0,
            "hr_bpm": hr,
            "peak_snr": round(peak_snr, 2),
            "periodicity": _periodicity(filt, fs, f0),
            "harmonic_ratio": _harmonic_ratio(freqs, power, f0),
            "harmonic_score": _harmonic_score(freqs, power, f0),
            "spectral_concentration": _spectral_concentration(freqs, power, f0),
            "spectral_q": _spectral_q_factor(freqs, power, f0),
            "hr_plausible": _hr_plausibility(f0, peak_snr),
        }

    # ── Global features ──────────────────────────────────────────────

    hrs = [v["hr_bpm"] for v in feat_per_region.values() if v["hr_bpm"] > 0]
    stability = float(np.var(hrs)) if len(hrs) >= 2 else 0.0

    coherence = _inter_region_coherence(filtered_signals)

    # Average f0 for phase coherence
    f0_vals = [v["f0_hz"] for v in feat_per_region.values() if v["f0_hz"] > 0]
    avg_f0 = float(np.mean(f0_vals)) if f0_vals else 0.0
    phase_coh = _phase_coherence(filtered_signals, fs, avg_f0)

    best_region_name = max(
        filtered_signals.keys(),
        key=lambda k: len(filtered_signals[k]),
        default=None,
    )
    if best_region_name is not None:
        best_filt = filtered_signals[best_region_name]
        best_f0 = feat_per_region[best_region_name]["f0_hz"]
        sdnn_ms, hrv_score = _hrv_proxy(best_filt, fs, best_f0)
        temporal_stability = _temporal_hr_stability(best_filt, fs)
        respiratory = _respiratory_modulation(best_filt, fs)
    else:
        sdnn_ms, hrv_score = 0.0, 0.0
        temporal_stability = 0.0
        respiratory = 0.0

    plausibility_scores = [v["hr_plausible"] for v in feat_per_region.values()]
    avg_hr_plausibility = float(np.mean(plausibility_scores)) if plausibility_scores else 0.0

    scr_scores = [v["spectral_concentration"] for v in feat_per_region.values()]
    avg_spectral_concentration = float(np.mean(scr_scores)) if scr_scores else 0.0

    periodicity_scores = [v["periodicity"] for v in feat_per_region.values()]
    avg_periodicity = float(np.mean(periodicity_scores)) if periodicity_scores else 0.0

    harmonic_scores = [v["harmonic_score"] for v in feat_per_region.values()]
    avg_harmonic = float(np.mean(harmonic_scores)) if harmonic_scores else 0.0

    q_scores = [v["spectral_q"] for v in feat_per_region.values()]
    avg_q = float(np.mean(q_scores)) if q_scores else 0.0

    liveness = {
        "hr_plausibility": avg_hr_plausibility,
        "spectral_concentration": avg_spectral_concentration,
        "spectral_sharpness": avg_q,
        "inter_region_coherence": coherence,
        "phase_coherence": phase_coh,
        "periodicity": avg_periodicity,
        "harmonic_structure": avg_harmonic,
        "hrv_score": hrv_score,
        "hrv_sdnn_ms": sdnn_ms,
        "temporal_hr_stability": temporal_stability,
        "respiratory_score": respiratory,
    }

    logger.info(
        f"Liveness features: SCR={avg_spectral_concentration:.3f}, Q={avg_q:.2f}, "
        f"coh={coherence:.3f}, phase_coh={phase_coh:.3f}, "
        f"HR_plaus={avg_hr_plausibility:.2f}, harmonic={avg_harmonic:.2f}, "
        f"periodicity={avg_periodicity:.2f}, HRV={hrv_score:.2f} (SDNN={sdnn_ms:.1f}ms), "
        f"temporal={temporal_stability:.2f}, respiratory={respiratory:.2f}"
    )

    for name, feat in feat_per_region.items():
        logger.info(
            f"  Region {name}: HR={feat['hr_bpm']:.0f}bpm, SNR={feat['peak_snr']:.1f}, "
            f"SCR={feat['spectral_concentration']:.3f}, Q={feat['spectral_q']:.2f}, "
            f"periodicity={feat['periodicity']:.3f}, harmonic={feat['harmonic_score']:.2f}"
        )

    return {
        "regions": feat_per_region,
        "stability": stability,
        "liveness": liveness,
    }
