"""Test ekstraksi fitur FEN (deterministik, tidak butuh artifact model)."""

from __future__ import annotations

import pytest

from app.ml import (
    FEATURE_NAMES,
    FenFeatureExtractor,
    extract_features,
    fen_to_vector,
    is_valid_fen,
)

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
# Setelah 1.e4: giliran hitam, en passant e3 (tapi tak ada pion hitam yang
# bisa menangkap, jadi en passant legal = tidak ada).
AFTER_E4_FEN = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
# Setelah 1.e4 d5 2.e5 f5: putih bisa menangkap en passant f5-f6 (ep square f6).
EP_LEGAL_FEN = "rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3"


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
    assert features["castling_rights"] == 4.0
    assert features["has_en_passant"] == 0.0


def test_time_features_absent_because_label_leakage() -> None:
    """BE-005: ply/fullmove/halfmove yang aturan label `phase` pakai tidak
    boleh jadi fitur — model harus menebak fase dari posisi, bukan aturan."""
    features = extract_features(START_FEN)
    assert "ply" not in features
    assert "fullmove_number" not in features
    assert "halfmove_clock" not in features
    assert all(name not in FEATURE_NAMES for name in ("ply", "fullmove_number", "halfmove_clock"))


def test_en_passant_only_when_capture_legal() -> None:
    # ep_square terisi tapi tak ada penangkap legal -> dianggap tidak ada.
    assert extract_features(AFTER_E4_FEN)["has_en_passant"] == 0.0
    assert extract_features(AFTER_E4_FEN)["side_to_move_white"] == 0.0
    # ep_square terisi dan pion putih e5 bisa menangkap di f6.
    assert extract_features(EP_LEGAL_FEN)["has_en_passant"] == 1.0


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
