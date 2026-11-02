"""Test logika evaluasi & smoke training model taktis."""

from __future__ import annotations

import numpy as np

from app.tactical import ATTACK_CLASSES
from app.tactical_training import build_pipeline, evaluate_multilabel

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
FORK_FEN = "7k/8/8/8/4n3/2R3Q1/8/7K w - - 0 1"


def test_evaluate_multilabel_perfect_prediction() -> None:
    classes = ATTACK_CLASSES[:3]
    y_true = np.array([[1, 0, 0], [0, 1, 1], [1, 1, 1], [0, 0, 1]], dtype=np.int8)
    y_proba = y_true.astype(float)

    metrics = evaluate_multilabel(y_true, y_proba, classes=classes)

    assert metrics["macro_average_precision"] == 1.0
    assert metrics["macro_f1"] == 1.0
    assert metrics["micro_f1"] == 1.0
    assert metrics["subset_accuracy"] == 1.0


def test_evaluate_multilabel_skips_class_without_positives() -> None:
    classes = ("hadir", "kosong")
    y_true = np.array([[1, 0], [1, 0], [0, 0]], dtype=np.int8)
    y_proba = np.array([[0.9, 0.2], [0.8, 0.2], [0.1, 0.2]])

    metrics = evaluate_multilabel(y_true, y_proba, classes=classes)

    assert metrics["per_class"]["kosong"]["average_precision"] is None
    assert metrics["per_class"]["kosong"]["f1"] is None
    assert metrics["macro_average_precision"] == 1.0


def test_build_pipeline_smoke_all_classes() -> None:
    fens = [START_FEN, FORK_FEN] * len(ATTACK_CLASSES)
    labels = np.zeros((len(fens), len(ATTACK_CLASSES)), dtype=np.int8)
    for index in range(len(ATTACK_CLASSES)):
        labels[index * 2, index] = 1
        labels[index * 2 + 1, index] = 1

    pipeline = build_pipeline(seed=0, max_iter=100)
    pipeline.fit(fens, labels)
    probabilities = pipeline.predict_proba(fens[:2])

    assert probabilities.shape == (2, len(ATTACK_CLASSES))
    assert np.all((probabilities >= 0.0) & (probabilities <= 1.0))
