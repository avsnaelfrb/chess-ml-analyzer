"""Siklus hidup proses engine: BE-006 (race spawn) & BE-008 (proses yatim).

Memakai engine tiruan supaya perilakunya bisa dipaksa (spawn lambat, crash)
tanpa biner Stockfish — dan tanpa membuka proses sungguhan di test.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import chess
import chess.engine
import pytest

from app.api import ModelNotLoadedError, MoveAnalyzer

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
ANALYZE_FEN = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
ANALYZE_UCI = "d2d4"


class _StubEngine:
    """Engine tiruan: lambat supaya jendela race terbuka lebar."""

    def __init__(self, delay: float = 0.05, crash: bool = False) -> None:
        self.delay = delay
        self.crash = crash
        self.id = {"name": "Stockfish 19 (stub)"}
        self.quit_calls = 0

    def _step(self) -> None:
        time.sleep(self.delay)
        if self.crash:
            raise chess.engine.EngineError("engine crash (stub)")

    def play(self, board, limit, **kwargs):
        self._step()
        return SimpleNamespace(move=next(iter(board.legal_moves)))

    def analyse(self, board, limit, **kwargs):
        self._step()
        return {}  # tanpa "score" -> _score_cp memberi 0.0; cukup untuk lifecycle

    def quit(self) -> None:
        self.quit_calls += 1


def _install(monkeypatch, spawns: list, delay: float = 0.05, crash: bool = False) -> None:
    def popen_uci(path: str) -> _StubEngine:
        engine = _StubEngine(delay=delay, crash=crash)
        spawns.append(engine)
        return engine

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", popen_uci)


def test_concurrent_cold_start_spawns_single_engine(monkeypatch) -> None:
    """BE-006: 8 request bersamaan pada cold start cuma boleh buka 1 proses."""
    spawns: list[_StubEngine] = []
    _install(monkeypatch, spawns, delay=0.1)

    analyzer = MoveAnalyzer(engine_path="/stub/stockfish")
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            moves = list(pool.map(lambda _: analyzer.best_move(START_FEN), range(8)))

        assert len(spawns) == 1
        assert len(set(moves)) == 1
    finally:
        analyzer.close()


def test_engine_error_on_best_move_quits_process(monkeypatch) -> None:
    """BE-008: engine crash harus ditutup, jangan jadi proses yatim."""
    spawns: list[_StubEngine] = []
    _install(monkeypatch, spawns, crash=True)

    analyzer = MoveAnalyzer(engine_path="/stub/stockfish")
    try:
        with pytest.raises(ModelNotLoadedError):
            analyzer.best_move(START_FEN)

        assert spawns[0].quit_calls == 1
        assert analyzer._engine is None

        # Request berikutnya harus spawn proses baru, bukan pakai yang mati.
        with pytest.raises(ModelNotLoadedError):
            analyzer.best_move(START_FEN)
        assert len(spawns) == 2
        assert spawns[1].quit_calls == 1
    finally:
        analyzer.close()


def test_engine_error_on_analyze_quits_process(monkeypatch) -> None:
    """BE-008: jalur analyze juga menutup engine yang crash."""
    spawns: list[_StubEngine] = []
    _install(monkeypatch, spawns, crash=True)

    analyzer = MoveAnalyzer(engine_path="/stub/stockfish")
    try:
        with pytest.raises(ModelNotLoadedError):
            analyzer.analyze(ANALYZE_FEN, ANALYZE_UCI)

        assert spawns[0].quit_calls == 1
        assert analyzer._engine is None
    finally:
        analyzer.close()
