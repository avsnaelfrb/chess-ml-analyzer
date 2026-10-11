"""Test fitur pola struktur pion (dobel, terisolasi, passed, pulau pion)."""

from __future__ import annotations

import chess

from app.ml import FEATURE_NAMES, extract_features, pawn_structure_features


def pls(fen: str) -> dict[str, float]:
    """Parser: FEN -> fitur struktur pion kedua warna."""
    return pawn_structure_features(chess.Board(fen))


def test_start_position_no_pawn_patterns() -> None:
    f = pls("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    for color in ("white", "black"):
        assert f[f"{color}_doubled_pawns"] == 0
        assert f[f"{color}_isolated_pawns"] == 0
        assert f[f"{color}_passed_pawns"] == 0
        assert f[f"{color}_pawn_islands"] == 1  # 8 file berurutan = 1 pulau


def test_doubled_pawns_counted_as_extras() -> None:
    # Hitam punya pion e2 & e3 (file sama) -> 1 pion dobel di sisi hitam.
    f = pls("8/8/8/8/8/4p3/4p3/8 w - - 0 1")
    assert f["black_doubled_pawns"] == 1
    assert f["white_doubled_pawns"] == 0
    # Keduanya terisolasi (file d & f kosong) dan passed (lawan tak ada).
    assert f["black_isolated_pawns"] == 2
    assert f["black_passed_pawns"] == 2


def test_isolated_pawn_without_neighbor_file() -> None:
    # Pion a8 sendirian -> terisolasi; tidak ada yang menghadang -> passed.
    f = pls("P7/8/8/8/8/8/8/8 b - - 0 1")
    assert f["white_isolated_pawns"] == 1
    assert f["white_passed_pawns"] == 1
    assert f["white_pawn_islands"] == 1


def test_neighboring_files_not_isolated() -> None:
    # Pion a2 & b2 saling bertetangga -> tidak ada yang terisolasi.
    f = pls("8/8/8/8/8/8/PP6/8 b - - 0 1")
    assert f["white_isolated_pawns"] == 0
    assert f["white_doubled_pawns"] == 0


def test_enemy_pawn_blocks_passed() -> None:
    # Pion putih a5 dihadang pion hitam b7 (file sejajar, lebih maju).
    f = pls("1p6/8/8/8/P7/8/8/8 b - - 0 1")
    assert f["white_passed_pawns"] == 0
    assert f["black_passed_pawns"] == 0  # b7 juga dihadang oleh a5
    assert f["white_isolated_pawns"] == 1
    assert f["black_isolated_pawns"] == 1


def test_passed_pawn_not_blocked() -> None:
    # Putih a5 vs hitam h6: file jauh, tidak saling menghadang -> kedua passed.
    f = pls("7p/8/8/8/P7/8/8/8 b - - 0 1")
    assert f["white_passed_pawns"] == 1
    assert f["black_passed_pawns"] == 1


def test_pawn_islands_split_by_gap() -> None:
    # Putih di file a, d, h -> 3 kelompok terpisah.
    f = pls("8/8/8/8/8/8/P2P3P/8 b - - 0 1")
    assert f["white_pawn_islands"] == 3
    assert f["white_isolated_pawns"] == 3


def test_pawn_features_inside_extract_features_and_feature_names() -> None:
    fen = "8/8/8/8/8/8/P2P3P/8 b - - 0 1"
    raw = extract_features(fen)
    for name in (
        "white_doubled_pawns",
        "white_isolated_pawns",
        "white_passed_pawns",
        "white_pawn_islands",
        "black_doubled_pawns",
        "black_isolated_pawns",
        "black_passed_pawns",
        "black_pawn_islands",
    ):
        assert name in FEATURE_NAMES
        assert name in raw
        assert raw[name] == pls(fen)[name]