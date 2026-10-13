"""Central configuration.

Semua path dan nilai yang bisa berubah dikumpulkan di sini supaya modul lain
tidak perlu tahu detail lokasi file. Nilai bisa dioverride lewat environment
variable (prefix ``CHESS_``).
"""

from __future__ import annotations

import os
from pathlib import Path

# backend/ (satu level di atas package ``app``)
BASE_DIR = Path(__file__).resolve().parent.parent

MODELS_DIR = BASE_DIR / "models"
DATASET_PATH = Path(os.getenv("CHESS_DATASET", BASE_DIR / "datasets" / "moves.csv"))
MODEL_PATH = Path(os.getenv("CHESS_MODEL", MODELS_DIR / "model.joblib"))
METRICS_PATH = Path(os.getenv("CHESS_METRICS", MODELS_DIR / "metrics.json"))

MODEL_VERSION = os.getenv("CHESS_MODEL_VERSION", "0.1.0")
MOVE_ANALYSIS_MODEL_VERSION = os.getenv("CHESS_MOVE_ANALYSIS_MODEL_VERSION", "0.2.0")

# Engine UCI untuk analisis langkah. Default: biner lokal di backend/bin/.
# Bisa diarahkan ke Stockfish sistem lewat CHESS_STOCKFISH_PATH (mis. "stockfish").
STOCKFISH_PATH = os.getenv("CHESS_STOCKFISH_PATH", str(BASE_DIR / "bin" / "stockfish"))
ENGINE_DEPTH = int(os.getenv("CHESS_ENGINE_DEPTH", "12"))

# Origin dev frontend (Vite). Dipisah koma kalau mau menambah origin lain.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CHESS_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
