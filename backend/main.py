"""Entrypoint ASGI.

Jalankan dengan:
    uv run uvicorn main:app --reload

Tiap request /api/* dicetak ke terminal (payload masuk & respons) oleh middleware
di ``app.api.create_app`` — berguna untuk memeriksa isi FEN/langkah yang dikirim
frontend. Log INFO diaktifkan di sini.
"""

import logging

from app.api import app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

__all__ = ["app"]
