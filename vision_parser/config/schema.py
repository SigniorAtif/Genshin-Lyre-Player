"""Configuration dataclasses for the Vision Parser pipeline.

All tuneable values live here. No magic numbers anywhere else in the codebase.
Load from JSON via InstrumentConfig.from_dict(); modify via config file, never in code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shared.constants import CANONICAL_KEY_SET


@dataclass(frozen=True)
class ROIBox:
    """Single key bounding box in pixel space at the reference resolution.

    Args:
        key: Key name (must be in CANONICAL_KEYS), e.g. "Q".
        x: Left edge, pixels from frame left.
        y: Top edge, pixels from frame top.
        w: Width in pixels.
        h: Height in pixels.
    """

    key: str
    x: int
    y: int
    w: int
    h: int

    def scale(self, sx: float, sy: float) -> ROIBox:
        """Return a copy with coordinates scaled by (sx, sy).

        Args:
            sx: Horizontal scale factor (actual_w / reference_w).
            sy: Vertical scale factor (actual_h / reference_h).

        Returns:
            New ROIBox with scaled integer coordinates. Width/height floored
            to at least 1 to avoid zero-size crops.
        """
        return ROIBox(
            key=self.key,
            x=int(self.x * sx),
            y=int(self.y * sy),
            w=max(1, int(self.w * sx)),
            h=max(1, int(self.h * sy)),
        )


@dataclass(frozen=True)
class ResolutionRef:
    """Reference resolution the ROI coordinates were calibrated at.

    Args:
        width: Frame width in pixels.
        height: Frame height in pixels.
    """

    width: int
    height: int


@dataclass(frozen=True)
class DetectionConfig:
    """Parameters controlling the rising-edge state machine and preprocessing.

    Args:
        threshold_rise: Intensity metric value that triggers IDLE→ACTIVE.
            For channel_mode="gray": pixel mean (0–255), default 185.
            For channel_mode="G_minus_R": G-R clipped to [0,255], default 40.
        threshold_fall: Intensity metric value below which ACTIVE→IDLE resets.
            Must be less than threshold_rise (hysteresis gap prevents chatter).
        cooldown_frames: Frames to stay blind after ACTIVE→IDLE transition.
            Prevents re-trigger from the tail glow of the previous press.
            Default 8 (≈133ms at 60fps).
        chord_window_frames: Max frame gap between two activations to treat
            them as a chord. Default 3 (≈50ms at 60fps).
        blur_kernel: Gaussian blur kernel size before intensity measurement.
            Must be odd. 0 = no blur. Default 3 (reduces H.264 block noise).
        channel_mode: Pixel metric to extract from each ROI.
            "gray"      — standard grayscale mean (default).
            "G_minus_R" — np.clip(G - R, 0, 255); detects green-glow press
                          animations where grayscale barely changes (e.g.
                          Genshin Lyre at 848x480).
    """

    threshold_rise: float
    threshold_fall: float
    cooldown_frames: int
    chord_window_frames: int
    blur_kernel: int
    channel_mode: str = "gray"
    # Per-key adaptive calibration deltas (used when calibrate_frames > 0).
    # Thresholds become: baseline_per_key + rise_delta / baseline_per_key + fall_delta.
    # This handles keys whose resting channel value is above threshold_fall (common
    # with G_minus_R mode where adjacent-key bleed raises the baseline unevenly).
    rise_delta: float = 25.0
    fall_delta: float = 3.0
    calibrate_frames: int = 60  # how many leading frames to sample for baseline


@dataclass(frozen=True)
class TimingConfig:
    """Parameters controlling beat quantization.

    Args:
        bpm: Beats per minute. Used as fallback; overridable at runtime.
        subdivisions: Available duration denominators, e.g. [1, 2, 4, 8].
            Duration assignment snaps to nearest value in this list.
        min_subdivision: Finest grid division. Must be in subdivisions.
            E.g. 8 means the grid resolution is 1/8 notes.
    """

    bpm: float
    subdivisions: list[int]
    min_subdivision: int


@dataclass(frozen=True)
class PanelCrop:
    """Optional pixel crop applied to each frame before any processing.

    Coordinates are in the full-frame pixel space at the reference resolution.
    When present, the frame is sliced to this rectangle first; all ROI box
    coordinates are then interpreted as relative to the crop origin (x, y).

    Benefits: smaller array through the entire pipeline (preprocessor blur,
    21× mean calls); cleaner debug frames showing only the key panel.

    Args:
        x: Left edge of the crop in the full frame.
        y: Top edge of the crop in the full frame.
        w: Width of the crop region.
        h: Height of the crop region.
    """

    x: int
    y: int
    w: int
    h: int

    def scale(self, sx: float, sy: float) -> "PanelCrop":
        """Return a copy scaled by (sx, sy)."""
        return PanelCrop(
            x=int(self.x * sx),
            y=int(self.y * sy),
            w=max(1, int(self.w * sx)),
            h=max(1, int(self.h * sy)),
        )


@dataclass
class InstrumentConfig:
    """Full configuration for a single instrument profile.

    Args:
        instrument: Human-readable instrument name, e.g. "lyre".
        resolution: Reference resolution the ROI coords were calibrated at.
        rois: Flattened list of all 21 ROI boxes in row-major key order.
            Coordinates are relative to panel_crop origin when panel_crop is set,
            otherwise relative to the full frame.
        detection: Rising-edge and preprocessing parameters.
        timing: Beat quantization parameters.
        panel_crop: Optional crop applied to each frame before preprocessing.
            ROI coordinates must be relative to this crop's (x, y) origin.
            None = use the full frame (default).
    """

    instrument: str
    resolution: ResolutionRef
    rois: list[ROIBox]
    detection: DetectionConfig
    timing: TimingConfig
    panel_crop: PanelCrop | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> InstrumentConfig:
        """Parse an InstrumentConfig from a JSON-derived dict.

        Args:
            d: Dict matching the lyre_1080p.json schema.

        Returns:
            Fully constructed InstrumentConfig.

        Raises:
            KeyError: If required fields are missing.
            ValueError: If a key name is not in CANONICAL_KEY_SET.
        """
        res = ResolutionRef(
            width=d["resolution"]["width"],
            height=d["resolution"]["height"],
        )

        rois: list[ROIBox] = []
        for row in d["rows"]:
            for k in row["keys"]:
                if k["key"] not in CANONICAL_KEY_SET:
                    raise ValueError(
                        f"Unknown key '{k['key']}' in ROI config. "
                        f"Expected one of {sorted(CANONICAL_KEY_SET)}"
                    )
                rois.append(ROIBox(key=k["key"], x=k["x"], y=k["y"], w=k["w"], h=k["h"]))

        det = d["detection"]
        detection = DetectionConfig(
            threshold_rise=float(det["threshold_rise"]),
            threshold_fall=float(det["threshold_fall"]),
            cooldown_frames=int(det["cooldown_frames"]),
            chord_window_frames=int(det["chord_window_frames"]),
            blur_kernel=int(det["blur_kernel"]),
            channel_mode=str(det.get("channel_mode", "gray")),
            rise_delta=float(det.get("rise_delta", 25.0)),
            fall_delta=float(det.get("fall_delta", 3.0)),
            calibrate_frames=int(det.get("calibrate_frames", 60)),
        )

        tim = d["timing"]
        timing = TimingConfig(
            bpm=float(tim["bpm"]),
            subdivisions=[int(s) for s in tim["subdivisions"]],
            min_subdivision=int(tim["min_subdivision"]),
        )

        panel_crop: PanelCrop | None = None
        if "panel_crop" in d:
            pc = d["panel_crop"]
            panel_crop = PanelCrop(x=int(pc["x"]), y=int(pc["y"]), w=int(pc["w"]), h=int(pc["h"]))

        return cls(
            instrument=d["instrument"],
            resolution=res,
            rois=rois,
            detection=detection,
            timing=timing,
            panel_crop=panel_crop,
        )

    @classmethod
    def from_json(cls, path: str | Path) -> InstrumentConfig:
        """Load an InstrumentConfig from a JSON file path.

        Args:
            path: Path to a JSON profile file (e.g. lyre_1080p.json).

        Returns:
            Parsed InstrumentConfig.
        """
        with open(path, encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))

    def scale_to(self, actual_w: int, actual_h: int) -> InstrumentConfig:
        """Return a copy with ROI boxes scaled to the actual video resolution.

        Args:
            actual_w: Video frame width in pixels.
            actual_h: Video frame height in pixels.

        Returns:
            New InstrumentConfig with scaled ROI boxes. All other fields
            are identical to the original.
        """
        sx = actual_w / self.resolution.width
        sy = actual_h / self.resolution.height
        return InstrumentConfig(
            instrument=self.instrument,
            resolution=ResolutionRef(width=actual_w, height=actual_h),
            rois=[roi.scale(sx, sy) for roi in self.rois],
            detection=self.detection,
            timing=self.timing,
            panel_crop=self.panel_crop.scale(sx, sy) if self.panel_crop else None,
        )
