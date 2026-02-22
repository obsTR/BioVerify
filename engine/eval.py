from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import analyze_video
from .config import Config


def _load_manifest(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def run_evaluation(
    manifest_path: str,
    out_dir: str,
    config: Optional[Config] = None,
    generator_type: Optional[str] = None,
    compression_level: Optional[str] = None,
) -> Dict[str, Any]:
    cfg = config or Config()
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)

    rows = _load_manifest(manifest_path)
    filtered: List[Dict[str, Any]] = []
    for r in rows:
        if generator_type and r.get("generator_type") != generator_type:
            continue
        if compression_level and r.get("compression_level") != compression_level:
            continue
        filtered.append(r)

    results: List[Dict[str, Any]] = []
    for row in filtered:
        video_path = row["path"]
        label = row.get("label", "")
        res = analyze_video(video_path, cfg).to_dict()
        results.append(
            {
                "path": video_path,
                "label": label,
                "verdict": res["verdict"],
                "score": res["score"],
                "sqi": res.get("metrics", {}).get("sqi", {}).get("aggregate"),
                "reasons": res.get("reasons", []),
            }
        )

    # Compute simple metrics
    tp = fp = tn = fn = inc = 0
    for r in results:
        label = r["label"]
        verdict = r["verdict"]
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

    total_decisive = tp + tn + fp + fn
    accuracy = (tp + tn) / total_decisive if total_decisive else 0.0
    tpr = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    inc_rate = inc / len(results) if results else 0.0

    report: Dict[str, Any] = {
        "config": asdict(cfg),
        "counts": {
            "tp": tp,
            "tn": tn,
            "fp": fp,
            "fn": fn,
            "inconclusive": inc,
        },
        "metrics": {
            "accuracy": accuracy,
            "tpr": tpr,
            "fpr": fpr,
            "inconclusive_rate": inc_rate,
        },
        "num_samples": len(results),
        "results": results,
    }

    json_path = root / "eval_report.json"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    md_path = root / "eval_report.md"
    md_lines = [
        "# Evaluation Report",
        "",
        f"- Samples: {len(results)}",
        f"- Accuracy: {accuracy:.3f}",
        f"- TPR: {tpr:.3f}",
        f"- FPR: {fpr:.3f}",
        f"- Inconclusive rate: {inc_rate:.3f}",
        "",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    return report

