"""Endpoint HTTP."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from .classifier import ModelNotLoadedError, PhaseClassifier
from .schemas import ClassifyRequest, ClassifyResponse, HealthResponse

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
