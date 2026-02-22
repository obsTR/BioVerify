from __future__ import annotations

import json
import logging
from typing import Any, Dict


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def log_params(logger: logging.Logger, step: str, params: Dict[str, Any]) -> None:
    logger.info("%s params: %s", step, json.dumps(params, sort_keys=True))

