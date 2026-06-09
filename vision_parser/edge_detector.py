"""Per-ROI rising-edge state machines for key-press detection."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, auto

import numpy as np

from vision_parser.config.schema import DetectionConfig

logger = logging.getLogger(__name__)


class EdgeState(Enum):
    """State of a single ROI's rising-edge detector."""
    IDLE = auto()
    ACTIVE = auto()


@dataclass
class ROIState:
    """Mutable per-ROI state.

    Args:
        state: Current detector state.
        cooldown_remaining: Frames remaining in post-release blind period.
        threshold_rise: Per-key absolute rise threshold (set by calibrate()).
        threshold_fall: Per-key absolute fall threshold (set by calibrate()).
    """
    state: EdgeState = EdgeState.IDLE
    cooldown_remaining: int = 0
    threshold_rise: float = 185.0
    threshold_fall: float = 140.0


@dataclass(frozen=True)
class TriggerEvent:
    """A detected key-press activation.

    Args:
        key: Key name (e.g. "A").
        frame_index: Frame number at which the trigger fired.
        timestamp_sec: Presentation timestamp of that frame in seconds.
        intensity: Channel metric value at the moment of trigger (diagnostic).
    """
    key: str
    frame_index: int
    timestamp_sec: float
    intensity: float


class EdgeDetector:
    """Rising-edge detector across all ROIs. Stateful — one instance per video run.

    Per-ROI state machine:
        IDLE  → ACTIVE  when intensity >= threshold_rise AND cooldown == 0
                        → emits TriggerEvent
        ACTIVE → IDLE   when intensity < threshold_fall
                        → starts cooldown countdown
        Cooldown counts down in IDLE; machine is blind during cooldown.

    Thresholds are per-key and set either from cfg globals (default) or via
    calibrate() which samples resting-state intensity and computes adaptive
    thresholds as: rise = baseline + cfg.rise_delta, fall = baseline + cfg.fall_delta.

    This is critical for channel modes like G_minus_R where different ROIs have
    different resting values — a global threshold_fall can leave high-baseline
    keys permanently stuck in ACTIVE after their first press.

    Args:
        cfg: DetectionConfig with thresholds, cooldown, and calibration params.
        keys: Ordered list of key names matching ROIManager.roi_boxes order.
    """

    def __init__(self, cfg: DetectionConfig, keys: list[str]) -> None:
        self._cfg = cfg
        self._keys = keys
        self._cooldown_frames = cfg.cooldown_frames
        self._states: dict[str, ROIState] = {
            k: ROIState(threshold_rise=cfg.threshold_rise, threshold_fall=cfg.threshold_fall)
            for k in keys
        }

    def calibrate(self, frames_intensities: list[dict[str, float]]) -> None:
        """Compute per-key adaptive thresholds from resting-state frame samples.

        Call this with the first N frames of intensities (before any notes play).
        Sets each key's thresholds to: baseline + rise_delta / baseline + fall_delta,
        where baseline is the per-key median intensity across the sample frames.

        Args:
            frames_intensities: List of dicts from ROIManager.extract_intensities(),
                one per sampled frame. Should come from silence (pre-song frames).
        """
        if not frames_intensities:
            return

        for key in self._keys:
            samples = [frame[key] for frame in frames_intensities if key in frame]
            if not samples:
                continue
            baseline = float(np.median(samples))
            rise = baseline + self._cfg.rise_delta
            fall = baseline + self._cfg.fall_delta
            self._states[key].threshold_rise = rise
            self._states[key].threshold_fall = fall
            logger.debug(
                "Calibrated key=%s baseline=%.1f rise=%.1f fall=%.1f",
                key, baseline, rise, fall,
            )

        logger.info(
            "EdgeDetector calibrated from %d frames. "
            "Example: key=%s rise=%.1f fall=%.1f",
            len(frames_intensities),
            self._keys[0],
            self._states[self._keys[0]].threshold_rise,
            self._states[self._keys[0]].threshold_fall,
        )

    def update(
        self,
        intensities: dict[str, float],
        frame_index: int,
        timestamp_sec: float,
    ) -> list[TriggerEvent]:
        """Process one frame's intensity readings and return any triggered events.

        Args:
            intensities: Dict from ROIManager.extract_intensities().
            frame_index: Current frame index.
            timestamp_sec: Current frame timestamp in seconds.

        Returns:
            List of TriggerEvents fired this frame (usually 0–2).
        """
        events: list[TriggerEvent] = []

        for key, intensity in intensities.items():
            state = self._states[key]

            if state.state == EdgeState.IDLE:
                if state.cooldown_remaining > 0:
                    state.cooldown_remaining -= 1
                elif intensity >= state.threshold_rise:
                    state.state = EdgeState.ACTIVE
                    event = TriggerEvent(
                        key=key,
                        frame_index=frame_index,
                        timestamp_sec=timestamp_sec,
                        intensity=intensity,
                    )
                    events.append(event)
                    logger.debug(
                        "TRIGGER key=%s frame=%d t=%.4fs intensity=%.1f (rise=%.1f)",
                        key, frame_index, timestamp_sec, intensity, state.threshold_rise,
                    )

            elif state.state == EdgeState.ACTIVE:
                if intensity < state.threshold_fall:
                    state.state = EdgeState.IDLE
                    state.cooldown_remaining = self._cooldown_frames

        return events

    def reset(self) -> None:
        """Reset all state machines to IDLE. Preserves calibrated thresholds."""
        for state in self._states.values():
            state.state = EdgeState.IDLE
            state.cooldown_remaining = 0
