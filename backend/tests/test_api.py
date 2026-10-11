"""Test untuk endpoint API."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sklearn.dummy import DummyClassifier
from sklearn.pipeline import Pipeline

from app.api import PhaseClassifier, create_app
from app.ml import FenFeatureExtractor

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
MID_FEN = "rnbqkbnr/pp2p1pp/2p2p2/3p4/3P1B2/5N2/PPP1PPPP/RN1QKB1R w KQkq - 0 4"
END_FEN = "3B2k1/p1p2ppp/1pn5/4pb2/8/1PP1KPP1/P2N3P/R6R b - - 0 22"


def _stub_classifier() -> PhaseClassifier:
    """Classifier tiruan: pipeline asli (validasi FEN) + DummyClassifier."""
    pipeline = Pipeline(
        steps=[
            ("features", FenFeatureExtractor()),
            ("clf", DummyClassifier(strategy="uniform", random_state=0)),
        ]
    )
    pipeline.fit(
        [START_FEN, MID_FEN, END_FEN, START_FEN],
        ["opening", "middlegame", "endgame", "opening"],
    )
    return PhaseClassifier(pipeline, model_version="test")


def make_client() -> TestClient:
    return TestClient(create_app(classifier=_stub_classifier()))


def test_health() -> None:
    client = make_client()
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_classify_returns_valid_contract() -> None:
    client = make_client()
    response = client.post("/api/classify", json={"fen": START_FEN})
    assert response.status_code == 200

    body = response.json()
    assert body["label"] in {"opening", "middlegame", "endgame"}
    assert 0.0 <= body["confidence"] <= 1.0
    assert set(body["probabilities"]) == {"opening", "middlegame", "endgame"}
    assert abs(sum(body["probabilities"].values()) - 1.0) < 1e-6
    assert body["model_version"] == "test"


def test_classify_invalid_fen_returns_422() -> None:
    client = make_client()
    response = client.post("/api/classify", json={"fen": "ini bukan fen"})
    assert response.status_code == 422


def test_classify_missing_fen_returns_422() -> None:
    client = make_client()
    response = client.post("/api/classify", json={})
    assert response.status_code == 422


def test_classify_without_model_returns_503() -> None:
    client = TestClient(create_app(classifier=PhaseClassifier(None)))
    response = client.post("/api/classify", json={"fen": START_FEN})
    assert response.status_code == 503
