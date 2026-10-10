"""Test ekstraksi fitur FEN (deterministik, tidak butuh artifact model)."""

from __future__ import annotations

import pytest

from app.ml.features import (
    FEATURE_NAMES,
    FenFeatureExtractor,
    extract_features,
    fen_to_vector,
    is_valid_fen,
)

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
# Setelah 1.e4: giliran hitam, en passant e3.
AFTER_E4_FEN = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"


def test_start_position_features() -> None:
    features = extract_features(START_FEN)
    assert features["material_total"] == 78
    assert features["material_white"] == 39
    assert features["material_black"] == 39
    assert features["piece_count_total"] == 32
    assert features["pawn_count_total"] == 16
    assert features["white_queen"] == 1
    assert features["black_queen"] == 1
    assert features["side_to_move_white"] == 1.0
    assert features["ply"] == 0.0
    assert features["fullmove_number"] == 1.0
    assert features["castling_rights"] == 4.0
    assert features["has_en_passant"] == 0.0


def test_en_passant_and_turn_detected() -> None:
    features = extract_features(AFTER_E4_FEN)
    assert features["has_en_passant"] == 1.0
    assert features["side_to_move_white"] == 0.0
    assert features["ply"] == 1.0  # hitam jalan, fullmove 1


@pytest.mark.parametrize(
    ("fen", "expected_ply"),
    [
        ("8/8/8/8/8/8/8/8 w - - 0 5", 8.0),
        ("8/8/8/8/8/8/8/8 b - - 0 5", 9.0),
    ],
)
def test_ply_derived_from_fullmove_and_side(fen: str, expected_ply: float) -> None:
    assert extract_features(fen)["ply"] == expected_ply


def test_castling_rights_count() -> None:
    assert extract_features("8/8/8/8/8/8/8/8 w Kq - 0 1")["castling_rights"] == 2.0
    assert extract_features("8/8/8/8/8/8/8/8 w - - 0 1")["castling_rights"] == 0.0


def test_fen_to_vector_matches_feature_names() -> None:
    vector = fen_to_vector(START_FEN)
    assert len(vector) == len(FEATURE_NAMES)
    assert all(isinstance(value, float) for value in vector)


def test_transformer_output_shape() -> None:
    extractor = FenFeatureExtractor()
    matrix = extractor.transform([START_FEN, AFTER_E4_FEN])
    assert matrix.shape == (2, len(FEATURE_NAMES))


def test_invalid_fen_raises_and_validator_flags() -> None:
    assert is_valid_fen(START_FEN) is True
    assert is_valid_fen("ini bukan fen") is False
    with pytest.raises(ValueError):
        extract_features("ini bukan fen")
