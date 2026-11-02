"""Test endpoint taktis (tanpa artifact hasil training)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from app.api import PhaseClassifier, TacticalClassifier, create_app

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


class _StubTacticModel:
    classes_ = np.array(["fork", "mate"])

    def predict_proba(self, X: list[str]) -> np.ndarray:
        return np.asarray([[0.2, 0.9] for _ in X])


def make_client(classifier: TacticalClassifier | None = None) -> TestClient:
    tactic = (
        classifier
        if classifier is not None
        else TacticalClassifier(
            _StubTacticModel(), classes=("fork", "mate"), model_version="test"
        )
    )
    return TestClient(
        create_app(classifier=PhaseClassifier(None), tactical_classifier=tactic)
    )


def test_classify_tactic_returns_sorted_labels() -> None:
    response = make_client().post("/api/classify-tactic", json={"fen": START_FEN})
    assert response.status_code == 200

    body = response.json()
    assert body["model_version"] == "test"
    assert body["labels"][0]["label"] == "mate"
    assert body["labels"][0]["probability"] == 0.9
    assert body["labels"][1]["label"] == "fork"
    assert 0.0 <= body["labels"][1]["probability"] <= 1.0


def test_classify_tactic_invalid_fen_returns_422() -> None:
    response = make_client().post("/api/classify-tactic", json={"fen": "bukan fen"})
    assert response.status_code == 422


def test_classify_tactic_without_model_returns_503() -> None:
    client = make_client(TacticalClassifier(None))
    response = client.post("/api/classify-tactic", json={"fen": START_FEN})
    assert response.status_code == 503


def test_corrupt_tactical_artifact_is_not_ready(tmp_path: Path) -> None:
    path = tmp_path / "black_attack.joblib"
    path.write_bytes(b"bukan joblib")
    assert not TacticalClassifier.from_path(path).ready
