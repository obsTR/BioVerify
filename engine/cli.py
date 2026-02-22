from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from . import analyze_video
from .config import Config
from .evidence import write_evidence
from .eval import run_evaluation
from .calibration import run_calibration


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="bioverify-engine")
    sub = parser.add_subparsers(dest="command", required=True)

    analyze_p = sub.add_parser("analyze", help="Analyze a video for liveness.")
    analyze_p.add_argument("video_path", help="Path to input video.")
    analyze_p.add_argument(
        "--out", dest="out_dir", required=True, help="Output folder for evidence."
    )
    # Placeholder for future config loading
    analyze_p.add_argument(
        "--config", dest="config_path", help="Optional JSON config file."
    )

    eval_p = sub.add_parser("eval", help="Run offline evaluation on a manifest CSV.")
    eval_p.add_argument("manifest", help="Path to manifest CSV.")
    eval_p.add_argument("--out", dest="out_dir", required=True, help="Output folder.")
    eval_p.add_argument("--config", dest="config_path", help="Optional JSON config.")
    eval_p.add_argument(
        "--generator_type",
        dest="generator_type",
        help="Optional filter by generator_type.",
    )
    eval_p.add_argument(
        "--compression_level",
        dest="compression_level",
        help="Optional filter by compression_level.",
    )

    calib_p = sub.add_parser("calibrate", help="Run calibration on a manifest CSV.")
    calib_p.add_argument("manifest", help="Path to manifest CSV.")
    calib_p.add_argument("--out", dest="out_dir", required=True, help="Output folder.")
    calib_p.add_argument("--config", dest="config_path", help="Optional JSON config.")

    return parser.parse_args(argv)


def _load_config(config_path: str | None) -> Config:
    if not config_path:
        return Config()
    p = Path(config_path)
    if not p.is_file():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    data: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    cfg = Config()
    # For now only allow ingest overrides at top level under "ingest"
    ingest_cfg = data.get("ingest")
    if ingest_cfg:
        for key, value in ingest_cfg.items():
            if hasattr(cfg.ingest, key):
                setattr(cfg.ingest, key, value)
    return cfg


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.command == "analyze":
        cfg = _load_config(getattr(args, "config_path", None))
        result = analyze_video(args.video_path, cfg)
        as_dict = result.to_dict()
        print(json.dumps(as_dict, indent=2, sort_keys=True))
        write_evidence(args.out_dir, as_dict, cfg, input_video_path=args.video_path)
        return 0

    if args.command == "eval":
        cfg = _load_config(getattr(args, "config_path", None))
        report = run_evaluation(
            args.manifest,
            args.out_dir,
            cfg,
            generator_type=getattr(args, "generator_type", None),
            compression_level=getattr(args, "compression_level", None),
        )
        print(json.dumps(report["metrics"], indent=2, sort_keys=True))
        return 0

    if args.command == "calibrate":
        cfg = _load_config(getattr(args, "config_path", None))
        result = run_calibration(args.manifest, args.out_dir, cfg)
        print(json.dumps(result["policy"], indent=2, sort_keys=True))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

