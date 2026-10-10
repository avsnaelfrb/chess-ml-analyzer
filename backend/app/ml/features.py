"""Ekstraksi fitur dari FEN.

Modul ini adalah **satu-satunya** sumber fitur, dipakai baik saat training
maupun saat inference. Ini penting: kalau training dan serving menghitung fitur
dengan cara berbeda, model akan menerima input yang tidak konsisten.

Representasi fitur: satu FEN -> satu vektor float dengan urutan tetap
:data:`FEATURE_NAMES`.
"""

from __future__ import annotations

from collections.abc import Sequence

import chess
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin

# Nilai material (raja = 0, tidak dihitung sebagai material).
PIECE_VALUES: dict[int, int] = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}

# Urutan piece untuk nama fitur.
PIECE_ORDER: tuple[tuple[int, str], ...] = (
    (chess.PAWN, "pawn"),
    (chess.KNIGHT, "knight"),
    (chess.BISHOP, "bishop"),
    (chess.ROOK, "rook"),
    (chess.QUEEN, "queen"),
    (chess.KING, "king"),
)

COLOR_ORDER: tuple[tuple[bool, str], ...] = (
    (chess.WHITE, "white"),
    (chess.BLACK, "black"),
)


def _build_feature_names() -> tuple[str, ...]:
    names: list[str] = []
    for _, color in COLOR_ORDER:
        names += [
            f"material_{color}",
            f"piece_count_{color}",
            f"pawn_count_{color}",
        ]
        for _, piece in PIECE_ORDER:
            names.append(f"{color}_{piece}")
    names += [
        "material_total",
        "piece_count_total",
        "pawn_count_total",
        "major_count_total",
        "minor_count_total",
        "side_to_move_white",
        "ply",
        "fullmove_number",
        "halfmove_clock",
        "castling_rights",
        "has_en_passant",
    ]
    return tuple(names)


FEATURE_NAMES: tuple[str, ...] = _build_feature_names()


def is_valid_fen(fen: str) -> bool:
    """Cek apakah FEN bisa diparse python-chess."""
    try:
        chess.Board(fen)
    except (ValueError, TypeError):
        return False
    return True


def extract_features(fen: str) -> dict[str, float]:
    """Ubah satu FEN menjadi dictionary fitur.

    Raises:
        ValueError: bila FEN tidak valid.
    """
    try:
        board = chess.Board(fen)
    except (ValueError, TypeError) as exc:  # normalisasi pesan error
        raise ValueError(str(exc)) from exc

    features: dict[str, float] = {}

    material_total = 0
    piece_count_total = 0
    pawn_count_total = 0
    major_total = 0
    minor_total = 0

    for color, color_name in COLOR_ORDER:
        material = 0
        piece_count = 0
        pawn_count = 0
        for piece_type, piece_name in PIECE_ORDER:
            count = len(board.pieces(piece_type, color))
            features[f"{color_name}_{piece_name}"] = float(count)
            piece_count += count
            pawn_count += count if piece_type == chess.PAWN else 0
            material += count * PIECE_VALUES[piece_type]
            major_total += count if piece_type in (chess.ROOK, chess.QUEEN) else 0
            minor_total += count if piece_type in (chess.KNIGHT, chess.BISHOP) else 0
        features[f"material_{color_name}"] = float(material)
        features[f"piece_count_{color_name}"] = float(piece_count)
        features[f"pawn_count_{color_name}"] = float(pawn_count)
        material_total += material
        piece_count_total += piece_count
        pawn_count_total += pawn_count

    fullmove = int(board.fullmove_number)
    ply = (fullmove - 1) * 2 + (0 if board.turn == chess.WHITE else 1)

    features["material_total"] = float(material_total)
    features["piece_count_total"] = float(piece_count_total)
    features["pawn_count_total"] = float(pawn_count_total)
    features["major_count_total"] = float(major_total)
    features["minor_count_total"] = float(minor_total)
    features["side_to_move_white"] = 1.0 if board.turn == chess.WHITE else 0.0
    features["ply"] = float(ply)
    features["fullmove_number"] = float(fullmove)
    features["halfmove_clock"] = float(board.halfmove_clock)
    features["castling_rights"] = float(bin(int(board.castling_rights)).count("1"))
    features["has_en_passant"] = 0.0 if board.ep_square is None else 1.0
    return features


def fen_to_vector(fen: str) -> list[float]:
    """Ubah satu FEN menjadi vektor float sesuai urutan :data:`FEATURE_NAMES`."""
    features = extract_features(fen)
    return [features[name] for name in FEATURE_NAMES]


class FenFeatureExtractor(BaseEstimator, TransformerMixin):
    """Transformer sklearn: iterable FEN -> matriks fitur.

    Dipasang sebagai langkah pertama pipeline supaya pipeline yang disimpan
    (``model.joblib``) sekaligus membawa logic ekstraksi fitur.
    """

    def fit(self, X: Sequence[str], y: object = None) -> "FenFeatureExtractor":
        return self

    def transform(self, X: Sequence[str]) -> np.ndarray:
        return np.asarray([fen_to_vector(fen) for fen in X], dtype=float)

    def get_feature_names_out(self, input_features: object = None) -> np.ndarray:
        return np.asarray(FEATURE_NAMES, dtype=object)
