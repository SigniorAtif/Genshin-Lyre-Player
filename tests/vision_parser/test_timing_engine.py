"""Unit tests for TimingEngine quantization and duration assignment."""

import pytest

from vision_parser.config.schema import TimingConfig
from vision_parser.edge_detector import TriggerEvent
from vision_parser.timing_engine import TimingEngine


@pytest.fixture
def cfg() -> TimingConfig:
    return TimingConfig(bpm=120.0, subdivisions=[1, 2, 4, 8], min_subdivision=8)


@pytest.fixture
def engine(cfg: TimingConfig) -> TimingEngine:
    return TimingEngine(cfg, fps=60.0)


def _trigger(key: str, t: float) -> TriggerEvent:
    return TriggerEvent(key=key, frame_index=int(t * 60), timestamp_sec=t, intensity=200.0)


class TestQuantize:
    def test_exact_grid_slot(self, engine: TimingEngine) -> None:
        # At BPM=120, min_sub=8: grid_duration = 0.0625s. t=0.5s → slot 8
        ev = _trigger("A", 0.5)
        result = engine.quantize([ev])
        assert result[0].grid_slot == 8
        assert result[0].quantization_error_sec == pytest.approx(0.0, abs=1e-6)

    def test_rounds_to_nearest_slot(self, engine: TimingEngine) -> None:
        # t=0.7833s → raw=12.53 → slot 13
        ev = _trigger("A", 0.7833)
        result = engine.quantize([ev])
        assert result[0].grid_slot == 13

    def test_error_within_half_grid(self, engine: TimingEngine) -> None:
        ev = _trigger("A", 0.7833)
        result = engine.quantize([ev])
        assert result[0].quantization_error_sec < engine.grid_duration_sec / 2 + 1e-9

    def test_multiple_events(self, engine: TimingEngine) -> None:
        evs = [_trigger("A", 0.0), _trigger("S", 0.5), _trigger("D", 1.0)]
        result = engine.quantize(evs)
        assert [r.grid_slot for r in result] == [0, 8, 16]


class TestAssignDurations:
    def test_eighth_note_sequence(self, engine: TimingEngine) -> None:
        # Two events one 1/8 note apart (1 grid slot)
        evs = [_trigger("A", 0.0), _trigger("S", 0.0625)]
        q = engine.quantize(evs)
        result = engine.assign_durations(q)
        # gap = 1 slot → denom = min_sub/1 = 8
        assert result[0][1] == 8

    def test_quarter_note(self, engine: TimingEngine) -> None:
        evs = [_trigger("A", 0.0), _trigger("S", 0.125)]
        q = engine.quantize(evs)
        result = engine.assign_durations(q)
        # gap = 2 slots → denom = 8/2 = 4
        assert result[0][1] == 4

    def test_half_note(self, engine: TimingEngine) -> None:
        evs = [_trigger("A", 0.0), _trigger("S", 0.25)]
        q = engine.quantize(evs)
        result = engine.assign_durations(q)
        # gap = 4 slots → denom = 8/4 = 2
        assert result[0][1] == 2

    def test_whole_beat(self, engine: TimingEngine) -> None:
        evs = [_trigger("A", 0.0), _trigger("S", 0.5)]
        q = engine.quantize(evs)
        result = engine.assign_durations(q)
        # gap = 8 slots → denom = 8/8 = 1
        assert result[0][1] == 1
