"""Test fitur taktis (deterministik, tanpa model/artifact)."""

from __future__ import annotations

import pytest

from app.tactical_features import (
    FEATURE_NAMES,
    TacticalFeatureExtractor,
    extract_tactical_features,
    tactical_vector,
)

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
# Hitam kuda e4 menyerang benteng c3 dan ratu g3.
FORK_FEN = "7k/8/8/8/4n3/2R3Q1/8/7K w - - 0 1"
# Kuda putih e2 dipin benteng hitam e8 ke raja e1.
PIN_FEN = "4r2k/8/8/8/8/8/4N3/4K3 w - - 0 1"
# Raja putih g1 tanpa pion pelindung di baris 2.
BACK_RANK_FEN = "r6k/8/8/8/8/8/8/6K1 w - - 0 1"
# Pion hitam b2, satu langkah dari promosi.
PROMOTION_FEN = "7k/8/8/8/8/8/1p6/7K w - - 0 1"
# Benteng hitam e8: uskup e4 di depan, ratu e2 di belakang.
SKEWER_FEN = "4r2k/8/8/8/4B3/8/4Q3/K7 w - - 0 1"
# Kuda hitam e2 menghalangi benteng e8 ke raja putih e1.
DISCOVERED_CHECK_FEN = "4r2k/8/8/8/8/8/4n3/4K3 w - - 0 1"
# Kuda putih c3 diserang uskup f6; pembelanya pion b2 diserang benteng b8.
DEFENDER_FEN = "1r5k/8/5b2/8/8/2N5/1P6/7K w - - 0 1"


def test_start_position_has_no_black_attack() -> None:
    features = extract_tactical_features(START_FEN)
    assert features["material_white"] == 39
    assert features["material_black"] == 39
    assert features["material_diff"] == 0
    assert features["attacked_white_count"] == 0
    assert features["attacked_white_value"] == 0
    assert features["hanging_white_count"] == 0
    assert features["white_king_attackers"] == 0
    assert features["white_king_ring_attacked"] == 0
    assert features["white_king_shield_pawns"] == 3
    assert features["white_king_open_files"] == 0
    assert features["is_check_white"] == 0
    assert features["white_pinned_count"] == 0
    assert features["black_skewer_targets"] == 0
    assert features["black_discovered_check_candidates"] == 0
    assert features["black_advanced_pawns"] == 0
    assert features["black_passed_pawns"] == 0
    assert features["white_back_rank_gaps"] == 0
    assert features["black_heavy_on_rank2"] == 0
    assert features["black_mobility"] == 20
    assert features["black_checks_available"] == 0
    assert features["black_captures_available"] == 0
    assert features["white_mobility"] == 20


def test_fork_targets_and_attacked_value() -> None:
    features = extract_tactical_features(FORK_FEN)
    assert features["black_fork_targets"] == 2
    assert features["attacked_white_count"] == 2
    assert features["attacked_white_value"] == 14
    assert features["defended_under_attack"] == 2
    assert features["defender_capturable"] == 2


def test_pinned_white_piece() -> None:
    features = extract_tactical_features(PIN_FEN)
    assert features["white_pinned_count"] == 1
    assert features["white_pinned_value"] == 3
    assert features["attacked_white_value"] == 3
    assert features["is_check_white"] == 0


def test_back_rank_gaps_and_open_file() -> None:
    features = extract_tactical_features(BACK_RANK_FEN)
    assert features["white_back_rank_gaps"] == 3
    assert features["white_king_shield_pawns"] == 0
    assert features["white_king_open_files"] == 3
    assert features["black_heavy_on_open_file"] == 1
    assert features["black_checks_available"] >= 1


def test_advanced_and_passed_black_pawn() -> None:
    features = extract_tactical_features(PROMOTION_FEN)
    assert features["black_advanced_pawns"] == 1
    assert features["black_passed_pawns"] == 1
    assert features["black_passed_advanced"] == 1
    assert features["black_pawns_ready_to_promote"] == 1


def test_skewer_geometry() -> None:
    features = extract_tactical_features(SKEWER_FEN)
    assert features["black_skewer_targets"] == 1
    assert features["black_discovered_candidates"] == 0


def test_discovered_check_geometry() -> None:
    features = extract_tactical_features(DISCOVERED_CHECK_FEN)
    assert features["black_discovered_check_candidates"] == 1
    assert features["is_check_white"] == 0


def test_defender_can_be_captured() -> None:
    features = extract_tactical_features(DEFENDER_FEN)
    assert features["defender_capturable"] == 1
    assert features["attacked_white_value"] == 4


def test_feature_vector_shape_and_extractor() -> None:
    vector = tactical_vector(START_FEN)
    assert len(vector) == len(FEATURE_NAMES)
    matrix = TacticalFeatureExtractor().fit_transform([START_FEN, FORK_FEN])
    assert matrix.shape == (2, len(FEATURE_NAMES))
    assert matrix.dtype == float


def test_invalid_fen_raises() -> None:
    with pytest.raises(ValueError):
        extract_tactical_features("bukan fen")
