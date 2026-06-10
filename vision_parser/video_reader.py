"""OpenCV video capture wrapper that yields typed frame packets."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Generator

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class FramePacket:
    """A single decoded video frame with timing metadata.

    Args:
        frame_index: 0-based monotonically increasing counter.
        timestamp_sec: Actual presentation timestamp from container metadata
            (from CAP_PROP_POS_MSEC), NOT derived from frame_index/fps.
            This is VFR-correct.
        bgr: Raw frame pixels, shape (H, W, 3), dtype uint8, BGR channel order.
    """

    frame_index: int
    timestamp_sec: float
    bgr: np.ndarray


class VideoReader:
    """Wraps cv2.VideoCapture and yields FramePackets until the video ends.

    Always reads timestamp from CAP_PROP_POS_MSEC (container DTS) rather than
    computing frame_index / fps. This is critical for VFR screen recordings
    where the declared FPS diverges from actual inter-frame intervals.

    Args:
        path: Filesystem path to the video file.

    Raises:
        FileNotFoundError: If the video file cannot be opened.
    """

    def __init__(self, path: str) -> None:
        self._cap = cv2.VideoCapture(path)
        if not self._cap.isOpened():
            raise FileNotFoundError(f"Could not open video: {path}")
        self._path = path
        logger.info(
            "Opened video '%s' — declared fps=%.2f, frame_count=%d",
            path,
            self.fps,
            self.frame_count,
        )

    @property
    def fps(self) -> float:
        """Declared FPS from container metadata.

        Note: For VFR video this is the nominal max FPS, not the actual
        inter-frame interval. Do not use for timing — use timestamp_sec.
        """
        return float(self._cap.get(cv2.CAP_PROP_FPS))

    @property
    def frame_count(self) -> int:
        """Total frame count from container metadata.

        Returns -1 for live captures or containers that don't report this.
        Use only for progress estimation — may be inaccurate for VFR video.
        """
        return int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))

    @property
    def width(self) -> int:
        """Frame width in pixels."""
        return int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))

    @property
    def height(self) -> int:
        """Frame height in pixels."""
        return int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def frames(self) -> Generator[FramePacket, None, None]:
        """Yield FramePackets for every decodeable frame.

        Skips blank/corrupted frames (ret=False or all-zero content) with a
        WARNING log, incrementing the frame index regardless to preserve timing.

        Yields:
            FramePacket for each successfully decoded frame.
        """
        frame_index = 0
        while True:
            timestamp_sec = self._cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            ret, bgr = self._cap.read()
            if not ret:
                break
            if bgr.max() == 0:
                logger.warning("Blank/corrupted frame at index %d (t=%.3fs) — skipped", frame_index, timestamp_sec)
                frame_index += 1
                continue
            yield FramePacket(frame_index=frame_index, timestamp_sec=timestamp_sec, bgr=bgr)
            frame_index += 1

    def reopen(self) -> None:
        """Release and re-open the video from the beginning.

        Use this to restart reading after a scan/detection pass that consumed
        some leading frames. More reliable than ``CAP_PROP_POS_FRAMES`` seek
        on H.264 streams (which can land on the wrong keyframe).
        """
        if self._cap.isOpened():
            self._cap.release()
        self._cap = cv2.VideoCapture(self._path)
        if not self._cap.isOpened():
            raise FileNotFoundError(f"Could not re-open video: {self._path}")
        logger.debug("Reopened capture from start: '%s'", self._path)

    def close(self) -> None:
        """Release the underlying VideoCapture.

        Safe to call multiple times.
        """
        if self._cap.isOpened():
            self._cap.release()
            logger.debug("Released capture for '%s'", self._path)
