"""Cross-module constants shared between vision_parser and player_engine."""

CANONICAL_KEYS: list[str] = [
    "Q", "W", "E", "R", "T", "Y", "U",
    "A", "S", "D", "F", "G", "H", "J",
    "Z", "X", "C", "V", "B", "N", "M",
]

CANONICAL_KEY_SET: frozenset[str] = frozenset(CANONICAL_KEYS)

ROW_SIZE: int = 7
NUM_ROWS: int = 3
NUM_KEYS: int = ROW_SIZE * NUM_ROWS  # 21
