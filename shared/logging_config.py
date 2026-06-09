"""Shared logging configuration for all pipeline modules."""

import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger with a consistent format.

    Args:
        level: Logging level (e.g. logging.DEBUG, logging.INFO).
            DEBUG emits per-ROI intensities and every trigger event.
            INFO emits pipeline milestones (video opened, complete, token count).
            WARNING emits quantization drift alerts, skipped frames, config oddities.
    """
    fmt = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
    datefmt = "%H:%M:%S"
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
