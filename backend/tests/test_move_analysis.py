"""Test endpoint analisis langkah (engine UCI / Stockfish)."""

from __future__ import annotations

import shutil
from pathlib import Path

import chess
import chess.engine
import pytest
from fastapi.testclient import TestClient

from app.api import MoveAnalyzer, PhaseClassifier, create_app, quality_from_cp_loss
from app.config import ENGINE_DEPTH, STOCKFISH_PATH

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
MISSING_ENGINE = "/nonexistent/stockfish"


def _client(analyzer: MoveAnalyzer) -> TestClient:
    return TestClient(create_app(classifier=PhaseClassifier(None), move_analyzer=analyzer))


def _engine_available() -> bool:
    return Path(STOCKFISH_PATH).exists() or shutil.which(STOCKFISH_PATH) is not None


def test_quality_thresholds_match_dataset() -> None:
    assert quality_from_cp_loss(0) == "Good"
    assert quality_from_cp_loss(49) == "Good"
    assert quality_from_cp_loss(50) == "Inaccuracy"
    assert quality_from_cp_loss(99) == "Inaccuracy"
    assert quality_from_cp_loss(100) == "Mistake"
    assert quality_from_cp_loss(199) == "Mistake"
    assert quality_from_cp_loss(200) == "Blunder"


def test_analyze_move_invalid_fen_returns_422() -> None:
    client = _client(MoveAnalyzer(engine_path=MISSING_ENGINE))
    response = client.post("/api/analyze-move", json={"fen_before": "bukan fen", "move_uci": "e2e4"})
    assert response.status_code == 422


def test_analyze_move_illegal_move_returns_422() -> None:
    client = _client(MoveAnalyzer(engine_path=MISSING_ENGINE))
    response = client.post("/api/analyze-move", json={"fen_before": START_FEN, "move_uci": "e2e5"})
    assert response.status_code == 422


def test_analyze_move_illegal_position_returns_422() -> None:
    # FEN bisa di-parse, tetapi ilegal: ratu a1 menyerang raja h8 saat giliran
    # putih. Stockfish akan mati bila ini sampai ke engine, jadi ditolak lebih dulu.
    client = _client(MoveAnalyzer(engine_path=MISSING_ENGINE))
    response = client.post(
        "/api/analyze-move",
        json={"fen_before": "r6k/8/8/8/8/8/7P/Q3K3 w - - 0 1", "move_uci": "a1a8"},
    )
    assert response.status_code == 422


def test_analyze_move_without_engine_returns_503() -> None:
    client = _client(MoveAnalyzer(engine_path=MISSING_ENGINE))
    response = client.post("/api/analyze-move", json={"fen_before": START_FEN, "move_uci": "e2e4"})
    assert response.status_code == 503


@pytest.mark.skipif(not _engine_available(), reason="biner Stockfish belum tersedia")
def test_best_move_scores_good_with_valid_contract() -> None:
    analyzer = MoveAnalyzer()
    try:
        engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
        info = engine.analyse(chess.Board(START_FEN), chess.engine.Limit(depth=ENGINE_DEPTH))
        best_uci = info["pv"][0].uci()
        engine.quit()

        client = _client(analyzer)
        response = client.post(
            "/api/analyze-move", json={"fen_before": START_FEN, "move_uci": best_uci}
        )
        assert response.status_code == 200

        body = response.json()
        assert body["quality"] == "Good"
        assert 0.0 <= body["cp_loss"] <= 20
        assert set(body["probabilities"]) == {"Good", "Inaccuracy", "Mistake", "Blunder"}
        assert body["probabilities"]["Good"] == 1.0
        assert abs(sum(body["probabilities"].values()) - 1.0) < 1e-6
    finally:
        analyzer.close()
