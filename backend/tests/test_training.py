"""Smoke test jalur training + pengawas kualitas metrik (BE-009).

Tanpa test ini pipeline pelatihan bisa rusak diam-diam: test lain hanya
memakai *artifact jadi* — dan artifact itu sendiri di-skip bila belum ada.
"""

from __future__ import annotations

import json
from pathlib import Path

import chess
import numpy as np
import pytest

from app.api import PhaseClassifier
from app.config import METRICS_PATH, MODEL_PATH
from app.ml import PHASES, build_pipeline, evaluate

# campuran posisi valid: 4 pembukaan, 4 tengah permainan, 3 akhir permainan
POSITIONS: list[tuple[str, str]] = [
    ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "opening"),
    ("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2", "opening"),
    ("rnb1kbnr/pppp1ppp/8/4p3/5P2/5N2/PPPPP1PP/RNBQKB1R b KQkq - 1 2", "opening"),
    ("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 6 4", "opening"),
    ("r1bq1rk1/pp2ppbp/2np1np1/8/3NP3/2N1B3/PPP1BPPP/R2Q1RK1 w - - 0 9", "middlegame"),
    ("2rq1rk1/pp1bppbp/2np1np1/8/3NP3/1BN1B3/PPP2PPP/R2Q1RK1 w - - 0 12", "middlegame"),
    ("r4rk1/1bq1bppp/p2ppn2/1p6/3N4/1BN1B3/PPP2PPP/R2Q1RK1 w - - 0 15", "middlegame"),
    ("8/5k2/8/8/8/4K3/4P3/8 w - - 0 40", "endgame"),
    ("4k3/8/8/8/8/8/4P3/4K3 w - - 0 50", "endgame"),
    ("8/8/4k3/8/8/3K4/8/3Q4 w - - 0 60", "endgame"),
]


def test_training_smoke_fit_predict_and_evaluate() -> None:
    """Jalankan training kecil lalu evaluasi, supaya jalur ini tak rusak diam-diam."""
    for fen, _ in POSITIONS:
        assert chess.Board(fen).is_valid(), f"FEN contoh tidak legal: {fen}"

    fens = [fen for fen, _ in POSITIONS]
    y = np.array([label for _, label in POSITIONS], dtype=object)

    pipeline = build_pipeline(seed=42, trees=5)
    pipeline.fit(fens, y)

    proba = pipeline.predict_proba(fens)
    labels = pipeline.predict(fens)
    assert set(labels) <= set(PHASES)
    assert np.allclose(proba.sum(axis=1), 1.0)

    metrics = evaluate(y, labels, proba, list(pipeline.classes_))
    assert 0.0 <= metrics["accuracy"] <= 1.0
    assert len(metrics["confusion_matrix"]) == len(PHASES)


def _read_metrics() -> dict:
    path = Path(METRICS_PATH)
    if not path.exists():
        pytest.skip("metrics.json belum ada; jalankan `uv run python train.py`")
    return json.loads(path.read_text(encoding="utf-8"))


def test_metrics_not_worse_than_majority_baseline() -> None:
    """Angka akurasi yang dilaporkan tidak boleh di bawah baseline tebak mayoritas.

    Menjaga agar "99,99%" tak lagi dikutip apa adanya: baseline-nya sendiri
    53% karena label terdistorsi, dan angka harus tetap di atasnya setelah
    fitur waktu dilepas (BE-005/BE-009).
    """
    metrics = _read_metrics()
    assert metrics["accuracy"] >= metrics["baseline_majority"]
    assert metrics["dedup_accuracy"] >= metrics["baseline_majority"]
    assert metrics["dedup_test_size"] > 0
    assert metrics["unseen_test_size"] > 0


def test_artifact_model_version_matches_metrics() -> None:
    """Versi yang disajikan API = versi yang tercatat saat artifact dilatih."""
    if not Path(MODEL_PATH).exists():
        pytest.skip("artifact model belum ada; jalankan `uv run python train.py`")
    metrics = _read_metrics()
    classifier = PhaseClassifier.from_path(MODEL_PATH)
    assert classifier.ready
    assert classifier.model_version == metrics["model_version"]
