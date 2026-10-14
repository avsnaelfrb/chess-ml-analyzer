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
import threading
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import chess
import chess.engine
import joblib
import numpy as np
from fastapi import APIRouter, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import (
    CORS_ORIGINS,
    ENGINE_DEPTH,
    MODEL_PATH,
    MODEL_VERSION,
    MOVE_ANALYSIS_MODEL_VERSION,
    STOCKFISH_PATH,
)
from .ml import PHASES

logger = logging.getLogger(__name__)

PhaseLabel = Literal["opening", "middlegame", "endgame"]
MoveQualityLabel = Literal["Good", "Inaccuracy", "Mistake", "Blunder"]

MOVE_QUALITIES: tuple[MoveQualityLabel, ...] = (
    "Good",
    "Inaccuracy",
    "Mistake",
    "Blunder",
)
MATE_SCORE = 10_000  # centipawn pengganti skor skakmat


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


class AnalyzeMoveRequest(BaseModel):
    fen_before: str = Field(
        ...,
        min_length=1,
        description="Posisi papan sebelum langkah dimainkan (FEN).",
        examples=["rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"],
    )
    move_uci: str = Field(
        ...,
        min_length=4,
        description="Langkah dalam notasi UCI (petak asal+tujuan + huruf promosi bila ada).",
        examples=["d2d4", "e7e8q", "b7b8n"],
    )


class MoveQualityProbabilities(BaseModel):
    Good: float = Field(..., ge=0.0, le=1.0)
    Inaccuracy: float = Field(..., ge=0.0, le=1.0)
    Mistake: float = Field(..., ge=0.0, le=1.0)
    Blunder: float = Field(..., ge=0.0, le=1.0)


class AnalyzeMoveResponse(BaseModel):
    quality: MoveQualityLabel
    cp_loss: float | None = Field(default=None)
    probabilities: MoveQualityProbabilities
    model_version: str


class BestMoveRequest(BaseModel):
    fen: str = Field(
        ...,
        min_length=1,
        description="Posisi giliran yang harus melangkah (FEN).",
        examples=["rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"],
    )


class BestMoveResponse(BaseModel):
    move_uci: str
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


# ============================== Analisis langkah ==============================

def quality_from_cp_loss(cp_loss: float) -> MoveQualityLabel:
    """Petakan centipawn loss ke label kualitas langkah.

    Ambangnya sama dengan definisi kolom ``move_quality`` di
    ``datasets/moves.csv``: Good <50, Inaccuracy 50-99, Mistake 100-199,
    Blunder >=200.
    """
    if cp_loss < 50:
        return "Good"
    if cp_loss < 100:
        return "Inaccuracy"
    if cp_loss < 200:
        return "Mistake"
    return "Blunder"


def _score_cp(info: dict, pov: chess.Color) -> float:
    """Ambil skor centipawn dari info engine, dari sudut pandang ``pov``."""
    score = info.get("score")
    if score is None:
        return 0.0
    return float(score.pov(pov).score(mate_score=MATE_SCORE))


@dataclass(frozen=True)
class MoveAnalysis:
    cp_loss: float
    quality: MoveQualityLabel


class MoveAnalyzer:
    """Menilai kualitas langkah memakai engine UCI (default Stockfish).

    Perbandingan: skor posisi sebelum langkah (langkah terbaik engine) versus
    skor setelah langkah dimainkan, keduanya dari sudut pandang pemain yang
    melangkah. Selisihnya = ``cp_loss``.

    Engine dijalankan malas (lazy) supaya server tetap start walau biner belum
    ada; kegagalan spawn diangkat sebagai :class:`ModelNotLoadedError` (503).
    """

    def __init__(
        self,
        engine_path: str | None = None,
        depth: int = ENGINE_DEPTH,
        model_version: str = MOVE_ANALYSIS_MODEL_VERSION,
    ) -> None:
        self._path = engine_path if engine_path is not None else STOCKFISH_PATH
        self._depth = depth
        self.model_version = model_version
        self._engine: chess.engine.SimpleEngine | None = None
        self._lock = threading.Lock()

    def _ensure_engine(self) -> chess.engine.SimpleEngine:
        if self._engine is None:
            try:
                self._engine = chess.engine.SimpleEngine.popen_uci(self._path)
            except Exception as exc:  # biner hilang / bukan engine
                raise ModelNotLoadedError(
                    f"Engine catur tidak bisa dijalankan dari {self._path!r}: {exc}"
                ) from exc
            name = self._engine.id.get("name")
            if name:
                self.model_version = name
        return self._engine

    def analyze(self, fen_before: str, move_uci: str) -> MoveAnalysis:
        try:
            board = chess.Board(fen_before)  # ValueError bila FEN tidak valid
        except ValueError as exc:
            raise ValueError(f"fen_before tidak valid: {exc}") from exc
        if not board.is_valid():
            # Mis. pihak yang tidak jalan sedang diskak; engine UCI menolak ini.
            raise ValueError("posisi fen_before tidak legal")

        try:
            move = chess.Move.from_uci(move_uci)
        except ValueError as exc:
            raise ValueError(f"move_uci tidak valid: {move_uci}") from exc
        if move not in board.legal_moves:
            raise ValueError("move_uci bukan langkah legal dari fen_before")

        engine = self._ensure_engine()
        limit = chess.engine.Limit(depth=self._depth)
        mover = board.turn
        try:
            with self._lock:
                before = engine.analyse(board, limit)
                board.push(move)
                after = engine.analyse(board, limit)
                board.pop()
        except chess.engine.EngineError as exc:
            # Engine mati: buang agar request berikutnya memulai proses baru.
            self._engine = None
            raise ModelNotLoadedError(f"Engine gagal menganalisis: {exc}") from exc

        cp_loss = max(0.0, _score_cp(before, mover) - _score_cp(after, mover))
        return MoveAnalysis(cp_loss=cp_loss, quality=quality_from_cp_loss(cp_loss))

    def best_move(self, fen: str) -> str:
        try:
            board = chess.Board(fen)  # ValueError bila FEN tidak valid
        except ValueError as exc:
            raise ValueError(f"fen tidak valid: {exc}") from exc
        if not board.is_valid():
            raise ValueError("posisi fen tidak legal")
        if board.is_game_over():
            raise ValueError("tidak ada langkah legal")

        engine = self._ensure_engine()
        limit = chess.engine.Limit(depth=self._depth)
        try:
            with self._lock:
                result = engine.play(board, limit)
        except chess.engine.EngineError as exc:
            # Engine mati: buang agar request berikutnya memulai proses baru.
            self._engine = None
            raise ModelNotLoadedError(f"Engine gagal mencari langkah: {exc}") from exc
        return result.move.uci()

    def close(self) -> None:
        if self._engine is not None:
            with self._lock:
                self._engine.quit()
            self._engine = None


# ============================== Endpoint ==============================

router = APIRouter(prefix="/api", tags=["api"])


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


@router.post("/analyze-move", response_model=AnalyzeMoveResponse)
def analyze_move(payload: AnalyzeMoveRequest, request: Request) -> AnalyzeMoveResponse:
    analyzer: MoveAnalyzer = request.app.state.move_analyzer

    try:
        analysis = analyzer.analyze(payload.fen_before, payload.move_uci)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except ModelNotLoadedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    quality = analysis.quality
    # Engine bersifat deterministik: satu kelas pasti, sisanya nol.
    probabilities = {q: (1.0 if q == quality else 0.0) for q in MOVE_QUALITIES}
    return AnalyzeMoveResponse(
        quality=quality,
        cp_loss=analysis.cp_loss,
        probabilities=MoveQualityProbabilities(**probabilities),
        model_version=analyzer.model_version,
    )


@router.post("/best-move", response_model=BestMoveResponse)
def best_move(payload: BestMoveRequest, request: Request) -> BestMoveResponse:
    analyzer: MoveAnalyzer = request.app.state.move_analyzer

    try:
        move_uci = analyzer.best_move(payload.fen)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except ModelNotLoadedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return BestMoveResponse(move_uci=move_uci, model_version=analyzer.model_version)


# ============================== App factory ==============================

def create_app(
    classifier: PhaseClassifier | None = None,
    move_analyzer: MoveAnalyzer | None = None,
) -> FastAPI:
    """Bangun instance FastAPI.

    Args:
        classifier: opsional, untuk injeksi (mis. pada test). Bila ``None``,
            model dimuat dari :data:`app.config.MODEL_PATH`.
        move_analyzer: opsional, untuk injeksi. Bila ``None``, engine UCI
            (Stockfish) disiapkan secara malas saat analisis pertama.
    """
    phase_classifier = (
        classifier if classifier is not None else PhaseClassifier.from_path(MODEL_PATH)
    )
    analyzer = move_analyzer if move_analyzer is not None else MoveAnalyzer()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        analyzer.close()  # matikan proses engine saat server berhenti

    app = FastAPI(
        title="Chess Classification API",
        version=MODEL_VERSION,
        description="Klasifikasi fase permainan catur (opening/middlegame/endgame) dari FEN.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.classifier = phase_classifier
    app.state.move_analyzer = analyzer

    app.include_router(router)
    return app


app = create_app()