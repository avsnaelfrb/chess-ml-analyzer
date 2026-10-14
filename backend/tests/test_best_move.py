"""Test endpoint langkah bot (`/api/best-move`, engine UCI / Stockfish)."""

from __future__ import annotations

import shutil
from pathlib import Path

import chess
import pytest
from fastapi.testclient import TestClient

from app.api import MoveAnalyzer, PhaseClassifier, create_app
from app.config import STOCKFISH_PATH

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
# Skakmat (fool's mate): putih tidak punya langkah legal.
MATE_FEN = "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"
MISSING_ENGINE = "/nonexistent/stockfish"


def _client(analyzer: MoveAnalyzer) -> TestClient:
    return TestClient(create_app(classifier=PhaseClassifier(None), move_analyzer=analyzer))


def _engine_available() -> bool:
    return Path(STOCKFISH_PATH).exists() or shutil.which(STOCKFISH_PATH) is not None


def test_best_move_invalid_fen_returns_422() -> None:
    client = _client(MoveAnalyzer(engine_path=MISSING_ENGINE))
    response = client.post("/api/best-move", json={"fen": "bukan fen"})
    assert response.status_code == 422


def test_best_move_illegal_position_returns_422() -> None:
    # Ratu a1 menyerang raja h8 saat giliran putih; engine UCI menolak posisi ini.
    client = _client(MoveAnalyzer(engine_path=MISSING_ENGINE))
    response = client.post("/api/best-move", json={"fen": "r6k/8/8/8/8/8/7P/Q3K3 w - - 0 1"})
    assert response.status_code == 422


def test_best_move_no_legal_move_returns_422() -> None:
    client = _client(MoveAnalyzer(engine_path=MISSING_ENGINE))
    response = client.post("/api/best-move", json={"fen": MATE_FEN})
    assert response.status_code == 422


def test_best_move_without_engine_returns_503() -> None:
    client = _client(MoveAnalyzer(engine_path=MISSING_ENGINE))
    response = client.post("/api/best-move", json={"fen": START_FEN})
    assert response.status_code == 503


@pytest.mark.skipif(not _engine_available(), reason="biner Stockfish belum tersedia")
def test_best_move_insufficient_material_still_plays() -> None:
    # Raja vs Raja: is_game_over() True (material tidak cukup) TAPI ada langkah legal.
    analyzer = MoveAnalyzer()
    try:
        client = _client(analyzer)
        fen = "8/8/8/4k3/8/4K3/8/8 b - - 0 1"
        response = client.post("/api/best-move", json={"fen": fen})
        assert response.status_code == 200

        body = response.json()
        assert chess.Move.from_uci(body["move_uci"]) in chess.Board(fen).legal_moves
    finally:
        analyzer.close()


@pytest.mark.skipif(not _engine_available(), reason="biner Stockfish belum tersedia")
def test_best_move_returns_legal_move() -> None:
    analyzer = MoveAnalyzer()
    try:
        client = _client(analyzer)
        response = client.post("/api/best-move", json={"fen": START_FEN})
        assert response.status_code == 200

        body = response.json()
        assert 4 <= len(body["move_uci"]) <= 5
        assert chess.Move.from_uci(body["move_uci"]) in chess.Board(START_FEN).legal_moves
        assert body["model_version"]
    finally:
        analyzer.close()
