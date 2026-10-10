"""Test karakterisasi perilaku model pada posisi terminal (skakmat).

Catatan penting
---------------
Test di sini **mengunci perilaku saat ini**, bukan menegaskan kebenaran
semantik. Temuan: label `phase` adalah fungsi dari nomor langkah + material,
sedangkan skakmat bisa terjadi di fase mana pun. Jadi posisi skakmat tetap
diklasifikasi sesuai fase di dataset, bukan "game over".

Skrip ini di-skip otomatis bila artifact model belum ada, supaya CI tanpa
`model.joblib` tetap hijau.
"""

from __future__ import annotations

from pathlib import Path

import chess
import pytest

from app.classifier import PhaseClassifier
from app.config import MODEL_PATH
from app.ml.labeling import PHASES

pytestmark = pytest.mark.skipif(
    not Path(MODEL_PATH).exists(),
    reason="artifact model belum ada; jalankan `uv run python -m app.ml.train`",
)

# Posisi skakmat yang benar (diverifikasi lewat python-chess di test ini).
SCHOLARS_MATE = "r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4"
FOOLS_MATE = "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"
KING_QUEEN_MATE = "7k/6Q1/5K2/8/8/8/8/8 b - - 0 1"
KING_ROOK_MATE = "R6k/8/6K1/8/8/8/8/8 b - - 0 1"

ALL_MATES = [SCHOLARS_MATE, FOOLS_MATE, KING_QUEEN_MATE, KING_ROOK_MATE]


@pytest.fixture(scope="module")
def classifier() -> PhaseClassifier:
    loaded = PhaseClassifier.from_path(MODEL_PATH)
    assert loaded.ready
    return loaded


def test_positions_are_actual_checkmates() -> None:
    for fen in ALL_MATES:
        board = chess.Board(fen)
        assert board.is_checkmate(), f"bukan skakmat: {fen}"


def test_checkmate_returns_valid_contract(classifier: PhaseClassifier) -> None:
    """Skakmat apa pun tetap menghasilkan respons sesuai kontrak (3 kelas)."""
    for fen in ALL_MATES:
        prediction = classifier.predict(fen)
        assert prediction.label in PHASES
        assert 0.0 <= prediction.confidence <= 1.0
        assert set(prediction.probabilities) == set(PHASES)
        assert abs(sum(prediction.probabilities.values()) - 1.0) < 1e-6


def test_early_checkmate_classified_by_move_number(classifier: PhaseClassifier) -> None:
    """Skakmat cepat (ply kecil) -> opening, karena fase ditentukan ply/material."""
    assert classifier.predict(SCHOLARS_MATE).label == "opening"
    assert classifier.predict(FOOLS_MATE).label == "opening"


def test_known_limitation_low_material_mate_at_ply_one(
    classifier: PhaseClassifier,
) -> None:
    """Batasan diketahui (OOD).

    Posisi K+Q vs K yang jelas endgame bagi manusia, tetapi di FEN ini
    `fullmove_number = 1`. Dataset tidak pernah memuat material rendah di ply
    rendah, sehingga model mengekstrapolasi ke default `middlegame`. Test ini
    sengaja mengunci perilaku tersebut; ubah bila fitur/model direvisi.
    """
    assert classifier.predict(KING_QUEEN_MATE).label == "middlegame"
