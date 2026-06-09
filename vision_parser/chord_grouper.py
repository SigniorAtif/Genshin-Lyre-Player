"""Groups near-simultaneous activations into chord tokens and inserts rests."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Union

from vision_parser.config.schema import DetectionConfig, TimingConfig
from vision_parser.timing_engine import QuantizedEvent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NoteToken:
    """A single key press.

    Args:
        key: Key name, e.g. "A".
        grid_slot: Absolute grid slot position.
        duration_denom: Duration as a note subdivision denominator.
            1 = whole beat, 2 = half, 4 = quarter, 8 = eighth.
    """

    key: str
    grid_slot: int
    duration_denom: int


@dataclass(frozen=True)
class ChordToken:
    """Two or more keys pressed simultaneously.

    Args:
        keys: Alphabetically sorted key names, e.g. ["A", "D", "S"].
        grid_slot: Absolute grid slot position (slot of the first key in group).
        duration_denom: Shared duration denominator for all keys in the chord.
    """

    keys: list[str]
    grid_slot: int
    duration_denom: int


@dataclass(frozen=True)
class RestToken:
    """A period of silence.

    Args:
        grid_slot: Absolute grid slot at which the rest begins.
        duration_denom: Duration denominator.
    """

    grid_slot: int
    duration_denom: int


Token = Union[NoteToken, ChordToken, RestToken]


class ChordGrouper:
    """Clusters near-simultaneous events into ChordTokens and inserts RestTokens.

    Chord window (in grid slots) is derived once at init:
        chord_window_sec = chord_window_frames / fps
        chord_window_slots = max(1, round(chord_window_sec / grid_duration_sec))

    Events within chord_window_slots of the first event in a group are merged.
    Gaps between groups that exceed chord_window_slots get RestTokens inserted.

    Args:
        detection_cfg: Source of chord_window_frames.
        timing_cfg: Source of min_subdivision and subdivisions.
        fps: Declared FPS from VideoReader (used to convert window to seconds).
        grid_duration_sec: Pre-computed grid slot duration in seconds
            (from TimingEngine.grid_duration_sec).
    """

    def __init__(
        self,
        detection_cfg: DetectionConfig,
        timing_cfg: TimingConfig,
        fps: float,
        grid_duration_sec: float,
    ) -> None:
        chord_window_sec = detection_cfg.chord_window_frames / fps
        self._window_slots = max(1, round(chord_window_sec / grid_duration_sec))
        self._min_subdivision = timing_cfg.min_subdivision
        self._subdivisions = sorted(timing_cfg.subdivisions)
        self._grid_duration_sec = grid_duration_sec
        logger.debug(
            "ChordGrouper: window=%d slots (%.1f frames, %.3fs)",
            self._window_slots,
            detection_cfg.chord_window_frames,
            chord_window_sec,
        )

    def group(
        self,
        quantized_events: list[QuantizedEvent],
        durations: list[tuple[QuantizedEvent, int]],
    ) -> list[Token]:
        """Build the final token list from quantized events and their durations.

        Args:
            quantized_events: QuantizedEvents sorted chronologically.
            durations: Parallel list of (QuantizedEvent, duration_denom) from
                TimingEngine.assign_durations().

        Returns:
            Flat ordered list of NoteToken, ChordToken, and RestToken objects,
            ready for TokenWriter.
        """
        if not quantized_events:
            return []

        dur_map: dict[int, int] = {id(ev): denom for ev, denom in durations}
        evs = list(quantized_events)

        # --- Pass 1: group into chords ---
        groups: list[list[QuantizedEvent]] = []
        current: list[QuantizedEvent] = [evs[0]]
        for ev in evs[1:]:
            if ev.grid_slot - current[0].grid_slot <= self._window_slots:
                current.append(ev)
            else:
                groups.append(current)
                current = [ev]
        groups.append(current)

        # --- Pass 2: build tokens and insert rests ---
        tokens: list[Token] = []
        prev_end_slot: int | None = None

        for group in groups:
            group_slot = group[0].grid_slot
            group_denom = dur_map[id(group[0])]  # representative duration

            # Insert rest if there is a gap since the last token's end
            if prev_end_slot is not None and group_slot > prev_end_slot:
                rest_tokens = self._make_rests(prev_end_slot, group_slot)
                tokens.extend(rest_tokens)

            if len(group) == 1:
                tokens.append(NoteToken(key=group[0].key, grid_slot=group_slot, duration_denom=group_denom))
            else:
                keys = sorted(ev.key for ev in group)
                tokens.append(ChordToken(keys=keys, grid_slot=group_slot, duration_denom=group_denom))

            prev_end_slot = group_slot + self._denom_to_slots(group_denom)

        return tokens

    def _denom_to_slots(self, denom: int) -> int:
        """Convert a duration denominator to a number of grid slots.

        Args:
            denom: Duration denominator (1, 2, 4, or 8).

        Returns:
            Number of grid slots. E.g. denom=4 with min_subdivision=8 → 2 slots.
        """
        if denom == 0:
            return self._min_subdivision
        return max(1, self._min_subdivision // denom)

    def _make_rests(self, start_slot: int, end_slot: int) -> list[RestToken]:
        """Fill a gap with the minimum number of RestTokens.

        Greedily uses the largest available subdivision that fits.

        Args:
            start_slot: First silent grid slot (inclusive).
            end_slot: First occupied grid slot (exclusive).

        Returns:
            List of RestTokens whose total duration equals end_slot - start_slot.
        """
        rests: list[RestToken] = []
        slot = start_slot
        remaining = end_slot - start_slot

        # Convert subdivisions to slot counts, descending (largest first)
        slot_options = sorted(
            [self._denom_to_slots(d) for d in self._subdivisions],
            reverse=True,
        )

        while remaining > 0:
            for slots in slot_options:
                if slots <= remaining:
                    denom = self._min_subdivision // slots
                    rests.append(RestToken(grid_slot=slot, duration_denom=denom))
                    slot += slots
                    remaining -= slots
                    break
            else:
                # Smallest subdivision still doesn't fit — use it anyway
                denom = self._min_subdivision
                rests.append(RestToken(grid_slot=slot, duration_denom=denom))
                slot += 1
                remaining -= 1

        return rests
