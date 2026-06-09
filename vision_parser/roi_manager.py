"""ROI management: scales bounding boxes to video resolution and extracts intensities."""

from __future__ import annotations

import logging
from typing import Any

import cv2
import numpy as np

from vision_parser.config.schema import InstrumentConfig, ROIBox

logger = logging.getLogger(__name__)


class ROIManager:
    """Scales ROI boxes to the actual video resolution and extracts mean intensities.

    Coordinates from the config JSON are defined at a reference resolution.
    At construction time this class computes scaled integer slice tuples for
    all 21 ROIs once; every subsequent intensity extraction is 21 np.mean() calls
    with no Python-level coordinate math.

    Args:
        cfg: InstrumentConfig whose rois are at cfg.resolution pixel space.
        video_w: Actual video frame width in pixels.
        video_h: Actual video frame height in pixels.
    """

    def __init__(self, cfg: InstrumentConfig, video_w: int, video_h: int) -> None:
        scaled_cfg = cfg.scale_to(video_w, video_h)
        self._boxes: list[ROIBox] = scaled_cfg.rois
        # Pre-compute slice objects for zero-overhead crop in the hot loop.
        self._slices: list[tuple[slice, slice]] = [
            (slice(b.y, b.y + b.h), slice(b.x, b.x + b.w))
            for b in self._boxes
        ]
        logger.debug(
            "ROIManager initialized — %d ROIs scaled from %dx%d to %dx%d",
            len(self._boxes),
            cfg.resolution.width,
            cfg.resolution.height,
            video_w,
            video_h,
        )

    @property
    def roi_boxes(self) -> list[ROIBox]:
        """Scaled ROI boxes in key-definition order."""
        return self._boxes

    def extract_intensities(self, gray: np.ndarray) -> dict[str, float]:
        """Compute mean pixel intensity for each ROI.

        Args:
            gray: Preprocessed grayscale frame, shape (H, W), dtype uint8.

        Returns:
            Dict mapping key name → mean intensity (float in [0.0, 255.0]).
        """
        return {
            box.key: float(np.mean(gray[row_sl, col_sl]))
            for box, (row_sl, col_sl) in zip(self._boxes, self._slices)
        }

    def debug_overlay(self, bgr: np.ndarray) -> np.ndarray:
        """Draw ROI bounding boxes onto a BGR frame copy.

        Useful for tools/roi_debugger.py to verify alignment.

        Args:
            bgr: BGR frame, shape (H, W, 3), dtype uint8.

        Returns:
            Copy of bgr with green rectangles and key labels drawn.
        """
        out = bgr.copy()
        for box in self._boxes:
            cv2.rectangle(out, (box.x, box.y), (box.x + box.w, box.y + box.h), (0, 255, 0), 1)
            cv2.putText(
                out,
                box.key,
                (box.x + 2, box.y + 14),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (0, 255, 0),
                1,
                cv2.LINE_AA,
            )
        return out
