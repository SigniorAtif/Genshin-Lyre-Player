"""Unit tests for ChordGrouper token construction."""

import pytest

from vision_parser.chord_grouper import ChordGrouper, ChordToken, NoteToken, RestToken
from vision_parser.config.schema import DetectionConfig, TimingConfig
from vision_parser.timing_engine import QuantizedEvent


@pytest.fixture
def detection_cfg() -> DetectionConfig:
    return DetectionConfig(
        threshold_rise=185.0,
        threshold_fall=140.0,
        cooldown_frames=8,
        chord_window_frames=3,
        blur_kernel=0,
    )


@pytest.fixture
def timing_cfg() -> TimingConfig:
    return TimingConfig(bpm=120.0, subdivisions=[1, 2, 4, 8], min_subdivision=8)


@pytest.fixture
def grouper(detection_cfg: DetectionConfig, timing_cfg: TimingConfig) -> ChordGrouper:
    # fps=60, grid_duration=0.0625s → chord_window_sec=3/60=0.05s
    # chord_window_slots = max(1, round(0.05/0.0625)) = max(1,1) = 1
    return ChordGrouper(detection_cfg, timing_cfg, fps=60.0, grid_duration_sec=0.0625)


def _qev(key: str, slot: int) -> QuantizedEvent:
    return QuantizedEvent(
        key=key,
        grid_slot=slot,
        beat_position=slot / 8.0,
        raw_timestamp_sec=slot * 0.0625,
        quantization_error_sec=0.0,
    )


class TestNoteAndChord:
    def test_single_note(self, grouper: ChordGrouper) -> None:
        ev = _qev("A", 0)
        tokens = grouper.group([ev], [(ev, 8)])
        assert len(tokens) == 1
        assert isinstance(tokens[0], NoteToken)
        assert tokens[0].key == "A"

    def test_chord_within_window(self, grouper: ChordGrouper) -> None:
        ev1, ev2 = _qev("A", 0), _qev("S", 1)
        tokens = grouper.group([ev1, ev2], [(ev1, 4), (ev2, 4)])
        assert len(tokens) == 1
        assert isinstance(tokens[0], ChordToken)
        assert sorted(tokens[0].keys) == ["A", "S"]

    def test_separate_notes_outside_window(self, grouper: ChordGrouper) -> None:
        ev1, ev2 = _qev("A", 0), _qev("S", 2)
        tokens = grouper.group([ev1, ev2], [(ev1, 8), (ev2, 8)])
        # gap = 2 > window_slots=1 → separate notes
        assert len(tokens) >= 2
        assert isinstance(tokens[0], NoteToken)

    def test_rest_inserted_in_gap(self, grouper: ChordGrouper) -> None:
        ev1, ev2 = _qev("A", 0), _qev("S", 8)
        tokens = grouper.group([ev1, ev2], [(ev1, 1), (ev2, 1)])
        # ev1 occupies slot 0 for 8 slots (denom=1 → 8 slots), ev2 at slot 8 → no gap
        # Actually let's use a larger gap:
        ev2 = _qev("S", 16)
        tokens = grouper.group([ev1, ev2], [(ev1, 1), (ev2, 1)])
        rest_tokens = [t for t in tokens if isinstance(t, RestToken)]
        assert len(rest_tokens) >= 1


class TestChordKeyOrdering:
    def test_keys_sorted_alphabetically(self, grouper: ChordGrouper) -> None:
        ev1, ev2, ev3 = _qev("D", 0), _qev("A", 0), _qev("S", 0)
        tokens = grouper.group([ev1, ev2, ev3], [(ev1, 4), (ev2, 4), (ev3, 4)])
        assert isinstance(tokens[0], ChordToken)
        assert tokens[0].keys == ["A", "D", "S"]
