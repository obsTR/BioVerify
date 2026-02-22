from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Tuple

import numpy as np
from scipy import signal

from .config import Config
from .types import IngestResult
from .utils.logging import get_logger, log_params
from .utils.video import read_video


logger = get_logger(__name__)


def _bandpass_filter(x: np.ndarray, fs: float, low: float, high: float) -> np.ndarray:
    if len(x) < 4:
        return x
    nyq = 0.5 * fs
    low_n = low / nyq
    high_n = high / nyq
    if low_n <= 0 or high_n >= 1 or low_n >= high_n:
        return x
    b, a = signal.butter(3, [low_n, high_n], btype="band")
    return signal.filtfilt(b, a, x)


def _roi_slices_from_box(h: int, w: int, box) -> Dict[str, tuple]:
    """Same ROI geometry as engine.roi: forehead, left/right cheek from face box."""
    if box is None or len(box) != 4:
        return {}
    x, y, fw, fh = box
    x, y = int(x), int(y)
    fw, fh = int(fw), int(fh)
    regions = {}
    r0, r1 = max(0, y), min(h, y + int(0.3 * fh))
    c0, c1 = max(0, x), min(w, x + fw)
    if r1 > r0 and c1 > c0:
        regions["forehead"] = (slice(r0, r1), slice(c0, c1))
    r0, r1 = max(0, y + int(0.3 * fh)), min(h, y + int(0.7 * fh))
    c0, c1 = max(0, x), min(w, x + int(0.5 * fw))
    if r1 > r0 and c1 > c0:
        regions["left_cheek"] = (slice(r0, r1), slice(c0, c1))
    r0, r1 = max(0, y + int(0.3 * fh)), min(h, y + int(0.7 * fh))
    c0, c1 = max(0, x + int(0.5 * fw)), min(w, x + fw)
    if r1 > r0 and c1 > c0:
        regions["right_cheek"] = (slice(r0, r1), slice(c0, c1))
    return regions


def _extract_chrom_signal(
    r_raw: np.ndarray, g_raw: np.ndarray, b_raw: np.ndarray
) -> np.ndarray:
    """
    CHROM (Chrominance-based) rPPG extraction.

    De Haan & Jeanne (2013): uses a linear combination of chrominance
    channels to cancel specular reflection and motion artifacts while
    preserving the blood-volume pulse.
    """
    n = len(r_raw)
    if n < 4:
        return g_raw

    r_mean = np.mean(r_raw)
    g_mean = np.mean(g_raw)
    b_mean = np.mean(b_raw)

    if r_mean < 1 or g_mean < 1 or b_mean < 1:
        return g_raw

    xs = r_raw / r_mean - 1.0
    ys = g_raw / g_mean - 1.0
    zs = b_raw / b_mean - 1.0

    s1 = 3.0 * xs - 2.0 * ys
    s2 = 1.5 * xs + ys - 1.5 * zs

    std_s1 = np.std(s1)
    std_s2 = np.std(s2)
    if std_s2 < 1e-10:
        return ys

    alpha = std_s1 / std_s2
    rppg = s1 - alpha * s2

    return rppg


def _extract_rgb_means_per_roi(
    frame: np.ndarray, roi_slices: Dict[str, tuple]
) -> Dict[str, Tuple[float, float, float]]:
    """Extract mean R, G, B for each ROI region in a single frame."""
    result = {}
    for name, sl in roi_slices.items():
        pixels = frame[sl]
        if pixels.size == 0:
            continue
        r_mean = float(np.mean(pixels[:, :, 2]))
        g_mean = float(np.mean(pixels[:, :, 1]))
        b_mean = float(np.mean(pixels[:, :, 0]))
        result[name] = (r_mean, g_mean, b_mean)
    return result


def extract_rppg(
    path: str,
    ingest_result: IngestResult,
    roi_metrics: Dict[str, Any],
    config: Config,
) -> Dict[str, Any]:
    """
    Extract rPPG signals per ROI using the CHROM method.

    Uses all three color channels (RGB) for robust pulse extraction,
    then bandpass filters and computes power spectra.
    """
    log_params(logger, "rppg", {"rppg": asdict(config.rppg)})

    frames, timestamps, fps = read_video(path)
    if len(frames) == 0:
        empty_region = {"raw": [], "filtered": [], "spectrum": {}}
        return {
            "metrics": {
                "times": [],
                "sampling_rate": float(fps),
                "regions": {n: dict(empty_region) for n in ["forehead", "left_cheek", "right_cheek"]},
            }
        }
    h, w = int(frames.shape[1]), int(frames.shape[2])

    roi_frames = roi_metrics.get("frames") or []
    region_names = ["forehead", "left_cheek", "right_cheek"]

    # Collect per-frame RGB means for each region
    rgb_per_region: Dict[str, List[Tuple[float, float, float]]] = {r: [] for r in region_names}
    times: List[float] = []

    for idx in range(len(timestamps)):
        if idx >= len(roi_frames):
            break
        t = float(timestamps[idx])
        frame_data = roi_frames[idx]
        box = frame_data.get("box")
        frame_regions = frame_data.get("regions") or {}
        if box is None:
            continue
        roi_slices = _roi_slices_from_box(h, w, box)
        if not roi_slices:
            continue

        rgb_means = _extract_rgb_means_per_roi(frames[idx], roi_slices)

        # Require all three regions for aligned time series
        frame_vals = {}
        for name in region_names:
            if name not in rgb_means:
                break
            region_info = frame_regions.get(name)
            if region_info is not None and not region_info.get("valid", True):
                break
            frame_vals[name] = rgb_means[name]

        if len(frame_vals) == len(region_names):
            for name in region_names:
                rgb_per_region[name].append(frame_vals[name])
            times.append(t)

    # Resample to uniform time grid when frames are scattered.
    # Without this, bandpass filter and FFT assume the wrong sample rate,
    # corrupting all spectral analysis and heart rate estimation.
    if len(times) >= 4:
        t_arr = np.array(times)
        t_start, t_end = float(t_arr[0]), float(t_arr[-1])
        span = t_end - t_start
        if span > 0:
            expected_n = int(round(span * fps))
            actual_n = len(times)
            if expected_n > actual_n * 1.1:
                t_uniform = np.linspace(t_start, t_end, expected_n)
                for name in region_names:
                    rgb_list = rgb_per_region[name]
                    if len(rgb_list) != actual_n:
                        continue
                    r_vals = np.array([v[0] for v in rgb_list])
                    g_vals = np.array([v[1] for v in rgb_list])
                    b_vals = np.array([v[2] for v in rgb_list])
                    rgb_per_region[name] = list(zip(
                        np.interp(t_uniform, t_arr, r_vals).tolist(),
                        np.interp(t_uniform, t_arr, g_vals).tolist(),
                        np.interp(t_uniform, t_arr, b_vals).tolist(),
                    ))
                logger.info(
                    f"Interpolated {actual_n} scattered samples to {expected_n} "
                    f"uniform samples (span={span:.1f}s, "
                    f"effective_rate={actual_n / span:.1f} -> {fps}fps)"
                )
                times = t_uniform.tolist()

    fs = float(fps)
    filtered_per_region: Dict[str, List[float]] = {}
    raw_green_per_region: Dict[str, List[float]] = {}
    spectra_per_region: Dict[str, Any] = {}

    for name in region_names:
        rgb_list = rgb_per_region[name]
        if len(rgb_list) < 4:
            filtered_per_region[name] = []
            raw_green_per_region[name] = []
            spectra_per_region[name] = {}
            continue

        r_arr = np.array([v[0] for v in rgb_list])
        g_arr = np.array([v[1] for v in rgb_list])
        b_arr = np.array([v[2] for v in rgb_list])

        raw_green_per_region[name] = g_arr.tolist()

        # CHROM extraction
        chrom_signal = _extract_chrom_signal(r_arr, g_arr, b_arr)

        # Detrend then bandpass
        x_detrend = signal.detrend(chrom_signal)
        x_filt = _bandpass_filter(
            x_detrend, fs, config.rppg.bandpass_low_hz, config.rppg.bandpass_high_hz
        )
        filtered_per_region[name] = x_filt.tolist()

        # Hann-windowed FFT for cleaner spectrum
        win = np.hanning(len(x_filt))
        x_win = x_filt * win
        freqs = np.fft.rfftfreq(len(x_win), d=1.0 / fs)
        power = np.abs(np.fft.rfft(x_win)) ** 2
        spectra_per_region[name] = {
            "freqs_hz": freqs.tolist(),
            "power": power.tolist(),
        }

    samples_per_region = {name: len(rgb_per_region[name]) for name in region_names}
    duration_seconds = (times[-1] - times[0]) if len(times) >= 2 else 0.0

    logger.info(
        f"rPPG CHROM extraction: {samples_per_region}, duration={duration_seconds:.1f}s, fs={fs}"
    )

    metrics: Dict[str, Any] = {
        "times": times,
        "sampling_rate": fs,
        "regions": {
            name: {
                "raw": raw_green_per_region.get(name, []),
                "filtered": filtered_per_region.get(name, []),
                "spectrum": spectra_per_region.get(name, {}),
            }
            for name in region_names
        },
        "summary": {
            "samples_per_region": samples_per_region,
            "duration_seconds": duration_seconds,
        },
    }

    return {"metrics": metrics}
