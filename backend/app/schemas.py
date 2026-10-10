"""Skema request/response API (kontrak FROZEN pada PLANNING.md)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PhaseLabel = Literal["opening", "middlegame", "endgame"]


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
