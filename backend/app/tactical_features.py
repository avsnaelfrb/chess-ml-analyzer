"""Fitur taktis dari FEN untuk klasifikasi pola serangan hitam.

Input selalu posisi giliran putih (posisi yang dikirim frontend). Karena motif
yang dipelajari adalah motif **hitam**, semua fitur diukur dari sudut pandang
hitam: seberapa besar tekanan hitam ke bidak/raja putih, potensi pin/skewer/
discovered, pion hitam yang maju, dan kelemahan baris belakang putih.

Modul ini terpisah dari ``app.ml`` (fitur fase) supaya pipeline fase yang sudah
beku tidak tersentuh.
"""

from __future__ import annotations

from collections.abc import Sequence

import chess
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin

PIECE_VALUES: dict[int, int] = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}

_LINE_DIRECTIONS: dict[int, tuple[tuple[int, int], ...]] = {
    chess.BISHOP: ((-1, -1), (-1, 1), (1, -1), (1, 1)),
    chess.ROOK: ((-1, 0), (1, 0), (0, -1), (0, 1)),
    chess.QUEEN: (
        (-1, -1),
        (-1, 1),
        (1, -1),
        (1, 1),
        (-1, 0),
        (1, 0),
        (0, -1),
        (0, 1),
    ),
}


def _build_feature_names() -> tuple[str, ...]:
    return (
        "material_white",
        "material_black",
        "material_diff",
        "white_king_file",
        "white_king_rank",
        "white_king_castled",
        "black_attackers_total",
        "attacked_white_count",
        "attacked_white_value",
        "hanging_white_count",
        "hanging_white_value",
        "max_attackers_on_white",
        "black_fork_targets",
        "defended_under_attack",
        "defender_capturable",
        "black_attacked_white_kingside",
        "black_attacked_white_queenside",
        "white_king_attackers",
        "white_king_ring_attackers",
        "white_king_ring_attacked",
        "white_king_ring_undefended",
        "white_king_shield_pawns",
        "white_king_open_files",
        "white_king_enemy_heavy_near",
        "is_check_white",
        "white_pinned_count",
        "white_pinned_value",
        "black_pinned_count",
        "black_skewer_targets",
        "black_discovered_candidates",
        "black_discovered_check_candidates",
        "white_pieces_without_defenders",
        "black_advanced_pawns",
        "black_passed_pawns",
        "black_passed_advanced",
        "black_pawns_ready_to_promote",
        "black_pawn_attacks_king_ring",
        "white_back_rank_gaps",
        "black_heavy_on_rank2",
        "black_heavy_on_open_file",
        "black_heavy_on_king_file",
        "black_mobility",
        "black_checks_available",
        "black_captures_available",
        "black_capture_value",
        "white_mobility",
    )


FEATURE_NAMES: tuple[str, ...] = _build_feature_names()


def _value(piece: chess.Piece | None) -> int:
    return PIECE_VALUES[piece.piece_type] if piece is not None else 0


def _line_targets(
    board: chess.Board,
) -> tuple[int, int, int]:
    """Hitung pin/skewer/discovered dari geometri bidak geser hitam.

    Mengembalikan ``(skewer, discovered, discovered_check)``:
    - skewer: bidak putih di depan, bidak putih lain (>=3) di belakangnya.
    - discovered: bidak hitam menghalangi, lalu bidak putih (>=3) di belakang.
    - discovered_check: seperti discovered tapi yang di belakang raja putih.
    """
    skewer = 0
    discovered = 0
    discovered_check = 0

    for square in chess.SquareSet(board.occupied_co[chess.BLACK]):
        piece = board.piece_at(square)
        if piece is None or piece.piece_type not in _LINE_DIRECTIONS:
            continue
        start_file = chess.square_file(square)
        start_rank = chess.square_rank(square)
        for d_file, d_rank in _LINE_DIRECTIONS[piece.piece_type]:
            seen: list[chess.Square] = []
            file, rank = start_file + d_file, start_rank + d_rank
            while 0 <= file < 8 and 0 <= rank < 8:
                target = chess.square(file, rank)
                occupant = board.piece_at(target)
                if occupant is not None:
                    seen.append(target)
                    if len(seen) == 2:
                        break
                file += d_file
                rank += d_rank

            if len(seen) < 2:
                continue
            front = board.piece_at(seen[0])
            back = board.piece_at(seen[1])
            if front is None or back is None:
                continue

            if front.color == chess.WHITE and back.color == chess.WHITE:
                if _value(back) >= 3 and _value(front) <= _value(back):
                    skewer += 1
            elif front.color == chess.BLACK and back.color == chess.WHITE:
                if back.piece_type == chess.KING:
                    discovered_check += 1
                elif _value(back) >= 3:
                    discovered += 1

    return skewer, discovered, discovered_check


def _pawn_features(board: chess.Board) -> dict[str, float]:
    white_pawns = board.pieces(chess.PAWN, chess.WHITE)
    black_pawns = board.pieces(chess.PAWN, chess.BLACK)
    white_pawn_files = {chess.square_file(sq) for sq in white_pawns}

    advanced = passed = passed_advanced = ready = pawn_attacks_ring = 0
    white_king = board.king(chess.WHITE)
    ring = set(board.attacks(white_king)) | {white_king} if white_king is not None else set()

    for sq in black_pawns:
        rank = chess.square_rank(sq)
        file = chess.square_file(sq)

        if rank <= 4:
            advanced += 1
        if rank <= 1:
            ready += 1

        is_passed = not any(
            chess.square_file(wp) in (file - 1, file, file + 1)
            and chess.square_rank(wp) < rank
            for wp in white_pawns
        )
        if is_passed:
            passed += 1
            if rank <= 4:
                passed_advanced += 1

        if board.attacks(sq) & ring:
            pawn_attacks_ring += 1

    return {
        "black_advanced_pawns": float(advanced),
        "black_passed_pawns": float(passed),
        "black_passed_advanced": float(passed_advanced),
        "black_pawns_ready_to_promote": float(ready),
        "black_pawn_attacks_king_ring": float(pawn_attacks_ring),
    }


def extract_tactical_features(fen: str) -> dict[str, float]:
    """Ekstrak fitur taktis dari satu FEN giliran putih.

    Raises:
        ValueError: bila FEN tidak valid.
    """
    try:
        board = chess.Board(fen)
    except (ValueError, TypeError) as exc:
        raise ValueError(str(exc)) from exc

    features: dict[str, float] = {}

    material_white = material_black = 0
    for square in chess.SquareSet(board.occupied_co[chess.WHITE]):
        material_white += _value(board.piece_at(square))
    for square in chess.SquareSet(board.occupied_co[chess.BLACK]):
        material_black += _value(board.piece_at(square))
    features["material_white"] = float(material_white)
    features["material_black"] = float(material_black)
    features["material_diff"] = float(material_black - material_white)

    white_king = board.king(chess.WHITE)
    if white_king is None:
        raise ValueError("FEN tidak punya raja putih")
    king_file = chess.square_file(white_king)
    king_rank = chess.square_rank(white_king)
    features["white_king_file"] = float(king_file)
    features["white_king_rank"] = float(king_rank)
    features["white_king_castled"] = float(
        king_rank == 0 and king_file in (6, 2)  # g1 / c1
    )

    white_pieces = board.occupied_co[chess.WHITE]
    black_attackers_total = 0
    attacked_count = attacked_value = 0
    hanging_count = hanging_value = 0
    max_attackers = 0
    defended_under_attack = defender_capturable = 0
    attacked_kingside = attacked_queenside = 0

    for sq in chess.SquareSet(white_pieces):
        piece = board.piece_at(sq)
        if piece is None or piece.piece_type == chess.KING:
            continue
        attackers = board.attackers(chess.BLACK, sq)
        if not attackers:
            continue

        value = _value(piece)
        black_attackers_total += len(attackers)
        attacked_count += 1
        attacked_value += value
        max_attackers = max(max_attackers, len(attackers))
        if chess.square_file(sq) >= 4:
            attacked_kingside += 1
        else:
            attacked_queenside += 1

        defenders = board.attackers(chess.WHITE, sq)
        if defenders:
            defended_under_attack += 1
            if len(defenders) == 1:
                defender_square = next(iter(defenders))
                defender = board.piece_at(defender_square)
                if (
                    defender is not None
                    and defender.piece_type != chess.KING
                    and board.attackers(chess.BLACK, defender_square)
                ):
                    defender_capturable += 1
        else:
            hanging_count += 1
            hanging_value += value

    features["black_attackers_total"] = float(black_attackers_total)
    features["attacked_white_count"] = float(attacked_count)
    features["attacked_white_value"] = float(attacked_value)
    features["hanging_white_count"] = float(hanging_count)
    features["hanging_white_value"] = float(hanging_value)
    features["max_attackers_on_white"] = float(max_attackers)
    features["defended_under_attack"] = float(defended_under_attack)
    features["defender_capturable"] = float(defender_capturable)
    features["black_attacked_white_kingside"] = float(attacked_kingside)
    features["black_attacked_white_queenside"] = float(attacked_queenside)

    # Potensi fork: berapa bidak putih (nilai >= 3) yang diserang satu bidak hitam.
    fork_targets = 0
    for sq in chess.SquareSet(board.occupied_co[chess.BLACK]):
        targets = board.attacks(sq) & white_pieces
        count = sum(
            1
            for target in targets
            if (piece := board.piece_at(target)) is not None
            and piece.piece_type != chess.KING
            and _value(piece) >= 3
        )
        fork_targets = max(fork_targets, count)
    features["black_fork_targets"] = float(fork_targets)

    # Keamanan raja putih.
    king_ring = set(board.attacks(white_king))
    king_ring_attacked = 0
    king_ring_undefended = 0
    for sq in king_ring:
        if board.is_attacked_by(chess.BLACK, sq):
            king_ring_attacked += 1
            if not board.is_attacked_by(chess.WHITE, sq):
                king_ring_undefended += 1

    enemy_heavy_near = 0
    king_zone = king_ring | {white_king}
    for sq in chess.SquareSet(board.occupied_co[chess.BLACK]):
        piece = board.piece_at(sq)
        if piece is not None and piece.piece_type in (chess.ROOK, chess.QUEEN):
            if board.attacks(sq) & king_zone:
                enemy_heavy_near += 1

    shield = 0
    open_files = 0
    for file in (king_file - 1, king_file, king_file + 1):
        if not 0 <= file < 8:
            continue
        if not any(chess.square_file(sq) == file for sq in board.pieces(chess.PAWN, chess.WHITE)):
            open_files += 1
        front_rank = king_rank + 1
        if front_rank < 8:
            if board.piece_at(chess.square(file, front_rank)) == chess.Piece(chess.PAWN, chess.WHITE):
                shield += 1

    features["white_king_attackers"] = float(len(board.attackers(chess.BLACK, white_king)))
    features["white_king_ring_attackers"] = float(
        sum(len(board.attackers(chess.BLACK, sq)) for sq in king_ring)
    )
    features["white_king_ring_attacked"] = float(king_ring_attacked)
    features["white_king_ring_undefended"] = float(king_ring_undefended)
    features["white_king_shield_pawns"] = float(shield)
    features["white_king_open_files"] = float(open_files)
    features["white_king_enemy_heavy_near"] = float(enemy_heavy_near)
    features["is_check_white"] = float(board.is_check())

    pinned_count = pinned_value = 0
    for sq in chess.SquareSet(white_pieces):
        if board.is_pinned(chess.WHITE, sq):
            pinned_count += 1
            pinned_value += _value(board.piece_at(sq))
    black_pinned = sum(
        1
        for sq in chess.SquareSet(board.occupied_co[chess.BLACK])
        if board.is_pinned(chess.BLACK, sq)
    )
    features["white_pinned_count"] = float(pinned_count)
    features["white_pinned_value"] = float(pinned_value)
    features["black_pinned_count"] = float(black_pinned)

    skewer, discovered, discovered_check = _line_targets(board)
    features["black_skewer_targets"] = float(skewer)
    features["black_discovered_candidates"] = float(discovered)
    features["black_discovered_check_candidates"] = float(discovered_check)

    features["white_pieces_without_defenders"] = float(
        sum(
            1
            for sq in chess.SquareSet(white_pieces)
            if (piece := board.piece_at(sq)) is not None
            and piece.piece_type != chess.KING
            and not board.attackers(chess.WHITE, sq)
        )
    )

    features.update(_pawn_features(board))

    # Baris belakang putih: berapa file di sekitar raja yang tidak punya pion
    # pelindung di baris 2.
    gaps = 0
    if king_rank == 0:
        for file in (king_file - 1, king_file, king_file + 1):
            if not 0 <= file < 8:
                continue
            if board.piece_at(chess.square(file, 1)) != chess.Piece(chess.PAWN, chess.WHITE):
                gaps += 1
    features["white_back_rank_gaps"] = float(gaps)

    white_pawn_files = {chess.square_file(sq) for sq in board.pieces(chess.PAWN, chess.WHITE)}
    heavy_rank2 = heavy_open = heavy_king_file = 0
    for sq in chess.SquareSet(board.occupied_co[chess.BLACK]):
        piece = board.piece_at(sq)
        if piece is None or piece.piece_type not in (chess.ROOK, chess.QUEEN):
            continue
        file = chess.square_file(sq)
        if chess.square_rank(sq) == 1:
            heavy_rank2 += 1
        if not any(chess.square_file(p) == file for p in chess.SquareSet(board.pawns)):
            heavy_open += 1
        if file == king_file and file not in white_pawn_files:
            heavy_king_file += 1
    features["black_heavy_on_rank2"] = float(heavy_rank2)
    features["black_heavy_on_open_file"] = float(heavy_open)
    features["black_heavy_on_king_file"] = float(heavy_king_file)

    # Mobilitas hitam "seandainya hitam melangkah sekarang" sebagai proksi
    # tekanan taktis laten. Papan asli tetap giliran putih.
    simulated = board.copy(stack=False)
    simulated.turn = chess.BLACK
    simulated.ep_square = None
    black_moves = list(simulated.legal_moves)
    checks = 0
    captures = 0
    capture_value = 0
    for move in black_moves:
        if simulated.gives_check(move):
            checks += 1
        if simulated.is_capture(move):
            captures += 1
            if not simulated.is_en_passant(move):
                capture_value += _value(simulated.piece_at(move.to_square))
            else:
                capture_value += 1
    features["black_mobility"] = float(len(black_moves))
    features["black_checks_available"] = float(checks)
    features["black_captures_available"] = float(captures)
    features["black_capture_value"] = float(capture_value)
    features["white_mobility"] = float(board.legal_moves.count())

    return features


def tactical_vector(fen: str) -> list[float]:
    """FEN -> vektor float sesuai urutan :data:`FEATURE_NAMES`."""
    features = extract_tactical_features(fen)
    return [features[name] for name in FEATURE_NAMES]


class TacticalFeatureExtractor(BaseEstimator, TransformerMixin):
    """Transformer sklearn: iterable FEN -> matriks fitur taktis."""

    def fit(self, X: Sequence[str], y: object = None) -> "TacticalFeatureExtractor":
        return self

    def transform(self, X: Sequence[str]) -> np.ndarray:
        return np.asarray([tactical_vector(fen) for fen in X], dtype=float)
