"""Renders the final token list to the .txt sheet music format."""

from __future__ import annotations

import logging
from typing import TextIO

from vision_parser.chord_grouper import ChordToken, NoteToken, RestToken, Token
from vision_parser.config.schema import TimingConfig

logger = logging.getLogger(__name__)


class TokenWriter:
    """Renders a list of Tokens to the .txt sheet music format.

    Output format:
        BPM 120
        A/4 S/4 D/2
        [ASD]/2 -
        Q/8 W/8 E/4 -/4

    Duration /1 (whole beat) is omitted by convention — bare key name only.
    Lines wrap at beat boundaries for readability.

    Args:
        cfg: TimingConfig (used for min_subdivision to determine beat boundaries).
        tokens_per_line: Approximate number of tokens per output line.
            Default 8 (one measure of 4/4 in eighth notes).
    """

    def __init__(self, cfg: TimingConfig, tokens_per_line: int = 8) -> None:
        self._min_subdivision = cfg.min_subdivision
        self._tokens_per_line = tokens_per_line

    def render(self, tokens: list[Token], bpm: float) -> str:
        """Render tokens to a complete file content string.

        Args:
            tokens: Ordered list of NoteToken, ChordToken, RestToken.
            bpm: Effective BPM (written as the first line).

        Returns:
            Full file content, newline-terminated.
        """
        lines: list[str] = [f"BPM {int(bpm) if bpm == int(bpm) else bpm}"]
        chunk: list[str] = []

        for i, tok in enumerate(tokens):
            chunk.append(self._format_token(tok))
            if len(chunk) >= self._tokens_per_line:
                lines.append(" ".join(chunk))
                chunk = []

        if chunk:
            lines.append(" ".join(chunk))

        content = "\n".join(lines) + "\n"
        logger.info("TokenWriter: rendered %d tokens, %d lines", len(tokens), len(lines))
        return content

    def write(self, tokens: list[Token], bpm: float, dest: TextIO) -> None:
        """Write rendered content to an open file handle.

        Args:
            tokens: Token list to render.
            bpm: Effective BPM.
            dest: Writable text file handle.
        """
        dest.write(self.render(tokens, bpm))

    @staticmethod
    def _format_token(tok: Token) -> str:
        """Format a single token as its string representation.

        Examples:
            NoteToken("A", denom=4)        → "A/4"
            NoteToken("A", denom=1)        → "A"   (whole note: omit /1)
            ChordToken(["A","D","S"], d=2) → "[ADS]/2"
            RestToken(denom=8)             → "-/8"
            RestToken(denom=1)             → "-"

        Args:
            tok: Any Token variant.

        Returns:
            String token representation.
        """
        if isinstance(tok, NoteToken):
            suffix = "" if tok.duration_denom == 1 else f"/{tok.duration_denom}"
            return f"{tok.key}{suffix}"
        elif isinstance(tok, ChordToken):
            keys = "".join(tok.keys)  # already sorted by ChordGrouper
            suffix = "" if tok.duration_denom == 1 else f"/{tok.duration_denom}"
            return f"[{keys}]{suffix}"
        elif isinstance(tok, RestToken):
            suffix = "" if tok.duration_denom == 1 else f"/{tok.duration_denom}"
            return f"-{suffix}"
        else:
            raise TypeError(f"Unknown token type: {type(tok)}")
