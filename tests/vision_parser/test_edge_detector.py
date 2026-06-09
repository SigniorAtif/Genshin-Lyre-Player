"""Unit tests for the EdgeDetector rising-edge state machine."""

import pytest

from vision_parser.config.schema import DetectionConfig
from vision_parser.edge_detector import EdgeDetector, EdgeState


@pytest.fixture
def cfg() -> DetectionConfig:
    return DetectionConfig(
        threshold_rise=185.0,
        threshold_fall=140.0,
        cooldown_frames=3,
        chord_window_frames=3,
        blur_kernel=0,
    )


@pytest.fixture
def detector(cfg: DetectionConfig) -> EdgeDetector:
    return EdgeDetector(cfg, keys=["A", "S"])


def _intensities(a: float = 0.0, s: float = 0.0) -> dict[str, float]:
    return {"A": a, "S": s}


class TestRisingEdge:
    def test_fires_on_rise(self, detector: EdgeDetector) -> None:
        events = detector.update(_intensities(a=190.0), frame_index=0, timestamp_sec=0.0)
        assert len(events) == 1
        assert events[0].key == "A"

    def test_does_not_fire_below_threshold(self, detector: EdgeDetector) -> None:
        events = detector.update(_intensities(a=150.0), frame_index=0, timestamp_sec=0.0)
        assert events == []

    def test_fires_only_once_while_active(self, detector: EdgeDetector) -> None:
        detector.update(_intensities(a=190.0), frame_index=0, timestamp_sec=0.0)
        events = detector.update(_intensities(a=195.0), frame_index=1, timestamp_sec=0.016)
        assert events == []

    def test_resets_after_fall(self, detector: EdgeDetector) -> None:
        detector.update(_intensities(a=190.0), frame_index=0, timestamp_sec=0.0)
        detector.update(_intensities(a=100.0), frame_index=1, timestamp_sec=0.016)  # fall below threshold_fall
        # cooldown_frames=3 — should be blind for 3 more frames
        events = detector.update(_intensities(a=190.0), frame_index=2, timestamp_sec=0.033)
        assert events == []

    def test_fires_again_after_cooldown(self, detector: EdgeDetector) -> None:
        detector.update(_intensities(a=190.0), frame_index=0, timestamp_sec=0.0)
        detector.update(_intensities(a=100.0), frame_index=1, timestamp_sec=0.016)
        for i in range(2, 5):  # 3 cooldown frames
            detector.update(_intensities(a=0.0), frame_index=i, timestamp_sec=i * 0.016)
        events = detector.update(_intensities(a=190.0), frame_index=5, timestamp_sec=0.083)
        assert len(events) == 1
        assert events[0].key == "A"

    def test_two_simultaneous_keys(self, detector: EdgeDetector) -> None:
        events = detector.update(_intensities(a=190.0, s=192.0), frame_index=0, timestamp_sec=0.0)
        assert len(events) == 2
        keys = {e.key for e in events}
        assert keys == {"A", "S"}

    def test_reset_clears_state(self, detector: EdgeDetector) -> None:
        detector.update(_intensities(a=190.0), frame_index=0, timestamp_sec=0.0)
        detector.reset()
        assert detector._states["A"].state == EdgeState.IDLE
        assert detector._states["A"].cooldown_remaining == 0
