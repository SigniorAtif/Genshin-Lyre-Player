"""Per-frame image preprocessing: optional crop, channel extraction, and blur."""

from __future__ import annotations

import cv2
import numpy as np

from vision_parser.config.schema import DetectionConfig, PanelCrop


class Preprocessor:
    """Stateless image preprocessor. One instance is reused across all frames.

    Pipeline per frame:
        1. Crop to panel_crop region (if configured) — reduces array size for
           all downstream work; ROI coords must be relative to this crop origin.
        2. Extract the detection channel:
               "gray"      → standard grayscale (cv2.COLOR_BGR2GRAY)
               "G_minus_R" → np.clip(G - R, 0, 255) as uint8; detects the
                             green-glow key press animation in Genshin Lyre
                             recordings where grayscale barely changes.
        3. Optional Gaussian blur to suppress H.264 block artifacts.

    Args:
        cfg: DetectionConfig supplying blur_kernel and channel_mode.
        panel_crop: Optional crop region to apply before channel extraction.
            Pass InstrumentConfig.panel_crop here. None = full frame.
    """

    _VALID_MODES = {"gray", "G_minus_R"}

    def __init__(self, cfg: DetectionConfig, panel_crop: PanelCrop | None = None) -> None:
        if cfg.blur_kernel != 0 and cfg.blur_kernel % 2 == 0:
            raise ValueError(
                f"blur_kernel must be 0 (disabled) or a positive odd integer; got {cfg.blur_kernel}"
            )
        if cfg.channel_mode not in self._VALID_MODES:
            raise ValueError(
                f"Unknown channel_mode '{cfg.channel_mode}'. Valid: {self._VALID_MODES}"
            )
        self._blur_kernel = cfg.blur_kernel
        self._channel_mode = cfg.channel_mode
        self._crop = panel_crop

    def crop(self, bgr: np.ndarray) -> np.ndarray:
        """Crop frame to the panel region if panel_crop is configured.

        Args:
            bgr: Full input frame, shape (H, W, 3), dtype uint8.

        Returns:
            Cropped BGR sub-array, or the original array if no crop is set.
            No copy is made — returned array shares memory with input.
        """
        if self._crop is None:
            return bgr
        c = self._crop
        return bgr[c.y : c.y + c.h, c.x : c.x + c.w]

    def to_channel(self, bgr: np.ndarray) -> np.ndarray:
        """Extract the configured detection channel from a BGR frame.

        Args:
            bgr: BGR frame (may already be cropped), shape (H, W, 3), uint8.

        Returns:
            Single-channel image, shape (H, W), dtype uint8.
        """
        if self._channel_mode == "gray":
            return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        elif self._channel_mode == "G_minus_R":
            g = bgr[:, :, 1].astype(np.int16)
            r = bgr[:, :, 2].astype(np.int16)
            return np.clip(g - r, 0, 255).astype(np.uint8)
        # Should never reach here — validated in __init__
        raise ValueError(f"Unknown channel_mode: {self._channel_mode}")

    def blur(self, channel: np.ndarray) -> np.ndarray:
        """Apply Gaussian blur to a single-channel image.

        Args:
            channel: Single-channel image, shape (H, W), uint8.

        Returns:
            Blurred image (same shape/dtype) if blur_kernel > 0,
            or the input array unchanged if blur_kernel == 0.
        """
        if self._blur_kernel == 0:
            return channel
        k = self._blur_kernel
        return cv2.GaussianBlur(channel, (k, k), 0)

    def process(self, bgr: np.ndarray) -> np.ndarray:
        """Full preprocessing pipeline: crop → channel → blur.

        Args:
            bgr: Raw BGR frame from VideoReader (full frame).

        Returns:
            Preprocessed single-channel image ready for ROI intensity extraction.
            Shape is (panel_crop.h, panel_crop.w) if panel_crop is set,
            else (frame_h, frame_w).
        """
        return self.blur(self.to_channel(self.crop(bgr)))
