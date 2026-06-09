"""Beat quantization: maps raw trigger timestamps to musical grid slots and durations."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from vision_parser.config.schema import TimingConfig
from vision_parser.edge_detector import TriggerEvent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QuantizedEvent:
    """A TriggerEvent snapped to the nearest musical grid slot.

    Args:
        key: Key name (e.g. "A").
        grid_slot: Integer grid slot from video start (0-based).
            One slot = 1/min_subdivision of a beat.
        beat_position: Fractional beat number (e.g. 1.5 = halfway through beat 2).
        raw_timestamp_sec: Original float timestamp from the video frame.
        quantization_error_sec: |raw - quantized| in seconds. Values above
            half a grid slot indicate BPM misconfiguration or player drift.
    """

    key: str
    grid_slot: int
    beat_position: float
    raw_timestamp_sec: float
    quantization_error_sec: float


class TimingEngine:
    """Converts raw TriggerEvents to QuantizedEvents and assigns durations.

    Stateless between calls — takes and returns full lists. The quantization
    is absolute (each event snapped independently) so errors do not accumulate.

    Worked example (BPM=120, min_subdivision=8, fps=60):
        beat_duration_sec = 60/120 = 0.5s
        grid_duration_sec = 0.5/8 = 0.0625s  (one 1/8-note slot)
        trigger at t=0.7833s → grid_slot = round(0.7833/0.0625) = 13
        quantized_t = 13 * 0.0625 = 0.8125s
        error = |0.7833 - 0.8125| = 0.0292s  (< half slot = 0.03125s ✓)

    Args:
        cfg: TimingConfig with BPM and subdivision settings.
        fps: Declared FPS from VideoReader (used only for logging context).
        bpm_override: If provided, overrides cfg.bpm.
    """

    def __init__(self, cfg: TimingConfig, fps: float, bpm_override: float | None = None) -> None:
        self._bpm = bpm_override if bpm_override is not None else cfg.bpm
        self._subdivisions = sorted(cfg.subdivisions)
        self._min_subdivision = cfg.min_subdivision
        self._fps = fps

        self._beat_duration = 60.0 / self._bpm
        self._grid_duration = self._beat_duration / self._min_subdivision
        self._half_grid = self._grid_duration / 2.0

        logger.info(
            "TimingEngine: bpm=%.1f, min_sub=%d, grid_duration=%.4fs",
            self._bpm,
            self._min_subdivision,
            self._grid_duration,
        )

    @property
    def bpm(self) -> float:
        """Effective BPM (may differ from config if bpm_override was supplied)."""
        return self._bpm

    @property
    def grid_duration_sec(self) -> float:
        """Duration of one grid slot in seconds."""
        return self._grid_duration

    def quantize(self, events: list[TriggerEvent]) -> list[QuantizedEvent]:
        """Snap each trigger to its nearest musical grid slot.

        Emits a WARNING if quantization_error_sec exceeds half a grid slot,
        which suggests the configured BPM is wrong or the player drifted.

        Args:
            events: Raw TriggerEvents from EdgeDetector, in chronological order.

        Returns:
            QuantizedEvents in the same order.
        """
        result: list[QuantizedEvent] = []
        for ev in events:
            grid_slot = round(ev.timestamp_sec / self._grid_duration)
            quantized_t = grid_slot * self._grid_duration
            error = abs(ev.timestamp_sec - quantized_t)
            beat_position = grid_slot / self._min_subdivision

            if error > self._half_grid:
                logger.warning(
                    "Large quantization error for key=%s at t=%.4fs: error=%.4fs > half_grid=%.4fs "
                    "(BPM drift or wrong BPM setting?)",
                    ev.key,
                    ev.timestamp_sec,
                    error,
                    self._half_grid,
                )

            result.append(
                QuantizedEvent(
                    key=ev.key,
                    grid_slot=grid_slot,
                    beat_position=beat_position,
                    raw_timestamp_sec=ev.timestamp_sec,
                    quantization_error_sec=error,
                )
            )
            logger.debug(
                "Quantized key=%s slot=%d beat=%.3f error=%.4fs",
                ev.key,
                grid_slot,
                beat_position,
                error,
            )

        return result

    def assign_durations(
        self, quantized: list[QuantizedEvent]
    ) -> list[tuple[QuantizedEvent, int]]:
        """Assign a duration denominator to each quantized event.

        Duration = gap to next event of any key (or end of song).
        The gap in grid slots is converted to a duration denominator by:
            denom = min_subdivision / gap_slots
        The result is clamped to the nearest value in cfg.subdivisions.

        Args:
            quantized: QuantizedEvents sorted by grid_slot (primary), key (secondary).

        Returns:
            List of (QuantizedEvent, duration_denominator) tuples.
            duration_denominator is an int from cfg.subdivisions, e.g. 4 means
            a quarter note (1/4 beat duration).
        """
        if not quantized:
            return []

        result: list[tuple[QuantizedEvent, int]] = []
        slots = [ev.grid_slot for ev in quantized]

        for i, ev in enumerate(quantized):
            if i + 1 < len(quantized):
                # Find the next event that is NOT at the same slot (chord partner)
                j = i + 1
                while j < len(quantized) and quantized[j].grid_slot == ev.grid_slot:
                    j += 1
                gap = quantized[j].grid_slot - ev.grid_slot if j < len(quantized) else self._min_subdivision
            else:
                gap = self._min_subdivision  # last note gets one whole beat

            denom = self._snap_duration(gap)
            result.append((ev, denom))

        return result

    def _snap_duration(self, gap_slots: int) -> int:
        """Convert a gap in grid slots to the nearest available duration denominator.

        Args:
            gap_slots: Number of grid slots between this event and the next.

        Returns:
            Duration denominator from cfg.subdivisions (e.g. 4 for a quarter note).
        """
        if gap_slots <= 0:
            return self._min_subdivision

        raw_denom = self._min_subdivision / gap_slots
        best = self._subdivisions[0]
        best_dist = abs(raw_denom - best)
        for sub in self._subdivisions[1:]:
            dist = abs(raw_denom - sub)
            if dist < best_dist:
                best = sub
                best_dist = dist
        return best
