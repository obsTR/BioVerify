from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import Config
from .eval import _load_manifest
from . import analyze_video


def _split_sets(rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    calib = [r for r in rows if r.get("set", "") == "calib"]
    eval_rows = [r for r in rows if r.get("set", "") == "eval"]
    return calib, eval_rows


def run_calibration(
    manifest_path: str,
    out_dir: str,
    config: Optional[Config] = None,
    target_fpr: float = 0.05,
) -> Dict[str, Any]:
    cfg = config or Config()
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)

    rows = _load_manifest(manifest_path)
    calib_rows, _eval_rows = _split_sets(rows)

    # Simple grid over tau_sqi and tau_auth
    best_cfg = None
    best_score = -1.0
    history: List[Dict[str, Any]] = []

    for tau_sqi in [0.2, 0.3, 0.4, 0.5]:
        for tau_auth in [0.4, 0.5, 0.6, 0.7]:
            cfg.quality.tau_sqi = tau_sqi
            cfg.scoring.tau_auth = tau_auth

            tp = fp = tn = fn = inc = 0
            for r in calib_rows:
                video_path = r["path"]
                label = r.get("label", "")
                res = analyze_video(video_path, cfg).to_dict()
                verdict = res["verdict"]
                if verdict == "Inconclusive":
                    inc += 1
                    continue
                if label == "Human":
                    if verdict == "Human":
                        tp += 1
                    else:
                        fn += 1
                elif label == "Synthetic":
                    if verdict == "Synthetic":
                        tn += 1
                    else:
                        fp += 1

            fpr = fp / (fp + tn) if (fp + tn) else 0.0
            tpr = tp / (tp + fn) if (tp + fn) else 0.0
            inc_rate = inc / len(calib_rows) if calib_rows else 0.0

            score = tpr - abs(fpr - target_fpr)
            history.append(
                {
                    "tau_sqi": tau_sqi,
                    "tau_auth": tau_auth,
                    "tpr": tpr,
                    "fpr": fpr,
                    "inconclusive_rate": inc_rate,
                    "score": score,
                }
            )
            if score > best_score:
                best_score = score
                best_cfg = (tau_sqi, tau_auth)

    if best_cfg is not None:
        cfg.quality.tau_sqi, cfg.scoring.tau_auth = best_cfg

    policy = {
        "config_version": cfg.config_version,
        "tau_sqi": cfg.quality.tau_sqi,
        "tau_auth": cfg.scoring.tau_auth,
        "target_fpr": target_fpr,
        "history": history,
    }

    policy_path = root / "policy_config.json"
    policy_path.write_text(json.dumps(policy, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "policy": policy,
        "config": asdict(cfg),
    }

