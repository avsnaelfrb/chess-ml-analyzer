"""App factory FastAPI: CORS, router, dan pemuatan model.

Pemuatan model dilakukan saat app dibuat (startup). Bila artifact belum ada,
app tetap jalan dan ``/api/classify`` mengembalikan 503 sehingga frontend bisa
berintegrasi lebih dulu.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .classifier import PhaseClassifier
from .config import CORS_ORIGINS, MODEL_PATH, MODEL_VERSION
from .routes import router


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
