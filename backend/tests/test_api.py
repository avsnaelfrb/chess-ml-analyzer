"""Test untuk endpoint API."""

from __future__ import annotations

from pathlib import Path

import joblib
from fastapi.testclient import TestClient
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline

from app.api import MAX_BODY_BYTES, PhaseClassifier, create_app
from app.ml import FEATURE_NAMES, FenFeatureExtractor

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


# --- BE-002: batas panjang input & ukuran badan ---


def test_fen_over_max_length_returns_422() -> None:
    fen = START_FEN.split(" ")[0] + " w KQkq - 0 " + "1" * 250  # sintaks sah, kepanjangan
    response = make_client().post("/api/classify", json={"fen": fen})
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "string_too_long"
    # Respons tetap pendek: pydantic memantulkan input, jadi ukurannya
    # mengikuti panjang request — yang sudah dibatasi lewat MAX_BODY_BYTES.
    assert len(response.text) < 2000


def test_oversize_body_returns_413() -> None:
    response = make_client().post("/api/classify", json={"fen": "x" * (MAX_BODY_BYTES + 1)})
    assert response.status_code == 413


# --- BE-007: FEN absurd dulu membuat float() overflow -> 500 ---


def test_classify_absurd_fullmove_returns_422() -> None:
    fen = START_FEN.rsplit(" ", 1)[0] + " 99999"  # pendek tapi nomor langkah gila
    assert make_client().post("/api/classify", json={"fen": fen}).status_code == 422


def test_classify_308_digit_fullmove_returns_422() -> None:
    fen = START_FEN.rsplit(" ", 1)[0] + " " + "9" * 308  # dulu OverflowError 500
    assert make_client().post("/api/classify", json={"fen": fen}).status_code == 422


# --- BE-004: artifact bermasalah harus 503, bukan crash saat import ---


def test_corrupt_model_artifact_is_not_ready(tmp_path: Path) -> None:
    path = tmp_path / "model.joblib"
    path.write_bytes(b"bukan joblib sama sekali")
    assert not PhaseClassifier.from_path(path).ready


def test_non_estimator_artifact_is_not_ready(tmp_path: Path) -> None:
    path = tmp_path / "model.joblib"
    joblib.dump({"bukan": "estimator"}, path)
    assert not PhaseClassifier.from_path(path).ready


def test_artifact_with_stale_feature_count_is_not_ready(tmp_path: Path, monkeypatch) -> None:
    """BE-004: artifact lama dengan jumlah fitur beda dari kode kini -> 503.

    Tanpa smoke predict, artifact begitu tetap "ter-load" lalu gagal di tiap
    request — dan sklearn melempar ValueError, yang terbaca sebagai 422 palsu.
    """
    pipeline = Pipeline(
        steps=[
            ("features", FenFeatureExtractor()),
            ("clf", RandomForestClassifier(n_estimators=3, random_state=0)),
        ]
    )
    pipeline.fit([START_FEN], ["opening"])
    path = tmp_path / "model.joblib"
    joblib.dump(pipeline, path)

    # Kode kini "meminta" satu fitur lebih sedikit daripada saat artifact dibuat.
    monkeypatch.setattr("app.ml.FEATURE_NAMES", FEATURE_NAMES[:-1])
    assert not PhaseClassifier.from_path(path).ready
