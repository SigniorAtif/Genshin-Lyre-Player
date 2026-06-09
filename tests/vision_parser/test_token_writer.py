"""Unit tests for TokenWriter rendering."""

import pytest

from vision_parser.chord_grouper import ChordToken, NoteToken, RestToken
from vision_parser.config.schema import TimingConfig
from vision_parser.token_writer import TokenWriter


@pytest.fixture
def cfg() -> TimingConfig:
    return TimingConfig(bpm=120.0, subdivisions=[1, 2, 4, 8], min_subdivision=8)


@pytest.fixture
def writer(cfg: TimingConfig) -> TokenWriter:
    return TokenWriter(cfg)


class TestFormatToken:
    def test_note_with_subdivision(self) -> None:
        tok = NoteToken(key="A", grid_slot=0, duration_denom=4)
        assert TokenWriter._format_token(tok) == "A/4"

    def test_note_whole_beat_omits_suffix(self) -> None:
        tok = NoteToken(key="A", grid_slot=0, duration_denom=1)
        assert TokenWriter._format_token(tok) == "A"

    def test_chord(self) -> None:
        tok = ChordToken(keys=["A", "D", "S"], grid_slot=0, duration_denom=2)
        assert TokenWriter._format_token(tok) == "[ADS]/2"

    def test_chord_whole_beat(self) -> None:
        tok = ChordToken(keys=["A", "S"], grid_slot=0, duration_denom=1)
        assert TokenWriter._format_token(tok) == "[AS]"

    def test_rest_eighth(self) -> None:
        tok = RestToken(grid_slot=0, duration_denom=8)
        assert TokenWriter._format_token(tok) == "-/8"

    def test_rest_whole(self) -> None:
        tok = RestToken(grid_slot=0, duration_denom=1)
        assert TokenWriter._format_token(tok) == "-"


class TestRender:
    def test_bpm_header(self, writer: TokenWriter) -> None:
        content = writer.render([], bpm=120.0)
        assert content.startswith("BPM 120\n")

    def test_bpm_float_preserved(self, writer: TokenWriter) -> None:
        content = writer.render([], bpm=112.5)
        assert content.startswith("BPM 112.5\n")

    def test_full_render(self, writer: TokenWriter) -> None:
        tokens = [
            NoteToken("A", 0, 4),
            NoteToken("S", 2, 4),
            ChordToken(["A", "S", "D"], 4, 2),
            RestToken(8, 8),
        ]
        content = writer.render(tokens, bpm=120.0)
        assert "A/4" in content
        assert "S/4" in content
        assert "[ASD]/2" in content
        assert "-/8" in content
        assert content.endswith("\n")
