"""Sisi HTTP: skema kontrak, pembungkus model, endpoint, dan app factory.

Sengaja digabung jadi satu modul supaya alur satu request bisa diikuti tanpa
lompat antar file:

    POST /api/classify {fen}
      -> PhaseClassifier.predict(fen)
         -> model.predict_proba([fen])   # Pipeline FEN -> fitur -> RF
      -> ClassifyResponse {label, confidence, probabilities, model_version}
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
from fastapi import APIRouter, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import CORS_ORIGINS, MODEL_PATH, MODEL_VERSION
from .ml import PHASES

logger = logging.getLogger(__name__)

PhaseLabel = Literal["opening", "middlegame", "endgame"]


# ============================== Skema kontrak API ==============================

class ClassifyRequest(BaseModel):
    fen: str = Field(
        ...,
        min_length=1,
        description="Posisi papan dalam notasi FEN.",
        examples=["rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"],
    )


class ProbabilityMap(BaseModel):
    opening: float = Field(..., ge=0.0, le=1.0)
    middlegame: float = Field(..., ge=0.0, le=1.0)
    endgame: float = Field(..., ge=0.0, le=1.0)


class ClassifyResponse(BaseModel):
    label: PhaseLabel
    confidence: float = Field(..., ge=0.0, le=1.0)
    probabilities: ProbabilityMap
    model_version: str


class HealthResponse(BaseModel):
    status: str = "ok"


# ============================== Pembungkus model ==============================

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
    def from_path(cls, path: str | Path = MODEL_PATH) -> PhaseClassifier:
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
        return Prediction(
            label=label, confidence=confidence, probabilities=probabilities
        )


# ============================== Endpoint ==============================

router = APIRouter(prefix="/api", tags=["classify"])


def _get_classifier(request: Request) -> PhaseClassifier:
    return request.app.state.classifier


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post("/classify", response_model=ClassifyResponse)
def classify(payload: ClassifyRequest, request: Request) -> ClassifyResponse:
    classifier = _get_classifier(request)

    if not classifier.ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model belum tersedia. Latih model terlebih dahulu.",
        )

    try:
        prediction = classifier.predict(payload.fen)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"FEN tidak valid: {exc}",
        ) from exc
    except ModelNotLoadedError as exc:  # pragma: no cover - dijaga di atas
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    return ClassifyResponse(
        label=prediction.label,
        confidence=prediction.confidence,
        probabilities=prediction.probabilities,
        model_version=classifier.model_version,
    )


# ============================== App factory ==============================

def create_app(classifier: PhaseClassifier | None = None) -> FastAPI:
    """Bangun instance FastAPI.

    Args:
        classifier: opsional, untuk injeksi (mis. pada test). Bila ``None``,
            model dimuat dari :data:`app.config.MODEL_PATH`.
    """
    app = FastAPI(
        title="Chess Classification API",
        version=MODEL_VERSION,
        description="Klasifikasi fase permainan catur (opening/middlegame/endgame) dari FEN.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.classifier = classifier if classifier is not None else PhaseClassifier.from_path(MODEL_PATH)

    app.include_router(router)
    return app


app = create_app()