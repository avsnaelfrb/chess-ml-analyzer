"""Pemuatan dataset fase permainan.

Dataset dibaca secara *streaming* per-chunk supaya file besar (~500 MB) tidak
perlu masuk memori sekaligus. Hanya kolom yang dibutuhkan yang diambil.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pandas as pd

# Kolom minimum untuk training fase: grup game, nomor langkah, FEN, label.
REQUIRED_COLUMNS: tuple[str, ...] = ("game_id", "ply", "fen_before", "phase")
FEN_COLUMN = "fen_before"
LABEL_COLUMN = "phase"
GROUP_COLUMN = "game_id"


def iter_chunks(
    path: str | Path,
    chunksize: int = 200_000,
    columns: tuple[str, ...] = REQUIRED_COLUMNS,
) -> Iterator[pd.DataFrame]:
    """Iterasi dataset sebagai potongan-potongan DataFrame."""
    for chunk in pd.read_csv(path, usecols=list(columns), chunksize=chunksize):
        yield chunk


def count_rows(path: str | Path) -> int:
    """Hitung jumlah baris data (tanpa header) dengan membaca file sekali."""
    with open(path, "rb") as handle:
        total = sum(1 for _ in handle)
    return max(total - 1, 0)


def load_frame(
    path: str | Path,
    limit: int | None = None,
    seed: int = 42,
    chunksize: int = 200_000,
) -> pd.DataFrame:
    """Muat dataset sebagai DataFrame.

    Args:
        path: lokasi CSV.
        limit: bila diisi, ambil sampel acak sekitar ``limit`` baris
            (hemat memori & waktu untuk eksperimen cepat).
        seed: seed sampling agar hasil reproducible.
    """
    if limit is None:
        return pd.concat(iter_chunks(path, chunksize), ignore_index=True)

    total = count_rows(path)
    frac = min(1.0, limit / total) if total else 1.0
    rng = np.random.default_rng(seed)

    parts: list[pd.DataFrame] = []
    for chunk in iter_chunks(path, chunksize):
        take = chunk.sample(frac=frac, random_state=int(rng.integers(0, 2**31 - 1)))
        if not take.empty:
            parts.append(take)

    frame = pd.concat(parts, ignore_index=True)
    if len(frame) > limit:
        frame = frame.sample(n=limit, random_state=seed).reset_index(drop=True)
    return frame
