"""Wrapper model klasifikasi fase.

Memuat artifact ``model.joblib`` (sebuah sklearn ``Pipeline`` yang di dalamnya
sudah termasuk :class:`~app.ml.features.FenFeatureExtractor`). Dengan begitu
serving cukup mengirim FEN mentah ke model.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from .config import MODEL_PATH, MODEL_VERSION
from .ml.labeling import PHASES

logger = logging.getLogger(__name__)


class ModelNotLoadedError(RuntimeError):
    """Dilempar saat prediksi diminta tetapi model belum tersedia."""


@dataclass(frozen=True)
class Prediction:
    label: str
    confidence: float
    probabilities: dict[str, float]


class PhaseClassifier:
    """Membungkus model sklearn untuk memprediksi fase dari FEN."""

    def __init__(self, model: Any | None = None, model_version: str = MODEL_VERSION):
        self._model = model
        self.model_version = model_version

    @property
    def ready(self) -> bool:
        return self._model is not None

    @classmethod
    def from_path(cls, path: str | Path = MODEL_PATH) -> "PhaseClassifier":
        path = Path(path)
        if not path.exists():
            logger.warning(
                "Model tidak ditemukan di %s. Endpoint /api/classify akan "
                "mengembalikan 503 sampai model dilatih.",
                path,
            )
            return cls(None)
        model = joblib.load(path)
        logger.info("Model dimuat dari %s", path)
        return cls(model)

    def predict(self, fen: str) -> Prediction:
        if self._model is None:
            raise ModelNotLoadedError("model belum dimuat")

        # Model menghitung fitur dari FEN; FEN invalid -> ValueError.
        probabilities_array = self._model.predict_proba([fen])[0]
        classes = [str(c) for c in self._model.classes_]
        probabilities = {c: float(p) for c, p in zip(classes, probabilities_array)}
        for phase in PHASES:
            probabilities.setdefault(phase, 0.0)

        label = max(probabilities, key=probabilities.get)
        confidence = float(probabilities[label])
        return Prediction(label=label, confidence=confidence, probabilities=probabilities)
