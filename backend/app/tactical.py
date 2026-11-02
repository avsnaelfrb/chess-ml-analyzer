"""Dataset taktis Lichess untuk klasifikasi pola serangan hitam.

Di dataset Lichess, ``FEN`` adalah posisi satu ply *sebelum* posisi puzzle:
``Moves[0]`` adalah langkah lawan solver. Jadi FEN dengan giliran putih berarti
solver-nya hitam. Itu persis posisi yang dikirim frontend saat user putih
menekan "Analisis posisi" di mode vs bot.

Modul ini sengaja terpisah dari ``app.ml`` supaya model fase yang sudah beku
tidak tersentuh. Dataset diunduh lewat HuggingFace ``datasets``, bukan file
parquet LFS di repo.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from datasets import Dataset, load_dataset

DATASET_ID = "Lichess/chess-puzzles"

# Theme yang dianggap motif serangan/taktik. Theme fase (opening/middlegame/
# endgame), panjang (short/long), keunggulan (crushing/advantage), dan sumber
# (master) sengaja tidak masuk.
ATTACK_THEMES: frozenset[str] = frozenset(
    {
        "fork",
        "pin",
        "skewer",
        "discoveredAttack",
        "xRayAttack",
        "deflection",
        "attraction",
        "clearance",
        "interference",
        "sacrifice",
        "discoveredCheck",
        "doubleCheck",
        "kingsideAttack",
        "queensideAttack",
        "attackingF2F7",
        "backRankMate",
        "exposedKing",
        "hangingPiece",
        "trappedPiece",
        "capturingDefender",
        "advancedPawn",
        "promotion",
        "mate",
    }
)


def fen_white_to_move(fen: str) -> bool:
    """True bila field giliran FEN adalah putih (solver puzzle = hitam)."""
    fields = fen.split()
    return len(fields) >= 2 and fields[1] == "w"


def attack_theme_labels(themes: list[str] | tuple[str, ...] | None) -> set[str]:
    """Ambil hanya theme motif serangan dari daftar ``Themes``."""
    return set(themes or ()) & ATTACK_THEMES


def is_black_attack_row(
    example: Mapping[str, Any],
    min_popularity: int = 50,
) -> bool:
    """Filter satu baris dataset untuk posisi serangan hitam yang layak.

    Syarat: giliran putih (solver hitam), punya minimal satu motif serangan,
    dan popularity tidak di bawah ambang.
    """
    if example.get("Popularity", 0) < min_popularity:
        return False
    if not fen_white_to_move(str(example.get("FEN", ""))):
        return False
    return bool(attack_theme_labels(example.get("Themes")))


def load_black_attack_dataset(
    split: str = "train",
    min_popularity: int = 50,
    limit: int | None = None,
    seed: int = 42,
) -> Dataset:
    """Muat dan filter dataset Lichess untuk pola serangan hitam.

    Args:
        split: split HuggingFace, dataset ini hanya punya ``train``.
        min_popularity: buang puzzle dengan ``Popularity`` di bawah nilai ini.
        limit: batasi jumlah baris setelah filter (``None`` = semua).
        seed: seed untuk sampling bila ``limit`` diisi.
    """
    # token=False: dataset publik; jangan pakai token tersimpan yang mungkin
    # sudah kedaluwarsa. Kalau HF_TOKEN di-set eksplisit, tetap dipakai.
    token = os.getenv("HF_TOKEN") or False
    dataset = load_dataset(DATASET_ID, split=split, token=token)
    dataset = dataset.filter(
        lambda row: is_black_attack_row(row, min_popularity=min_popularity)
    )
    if limit is not None and limit > 0 and len(dataset) > limit:
        dataset = dataset.shuffle(seed=seed).select(range(limit))
    return dataset
