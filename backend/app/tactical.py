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
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
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

# Urutan kelas tetap dan deterministik: dipakai untuk membangun vektor label
# sekaligus urutan probabilitas saat serving.
ATTACK_CLASSES: tuple[str, ...] = tuple(sorted(ATTACK_THEMES))


def fen_white_to_move(fen: str) -> bool:
    """True bila field giliran FEN adalah putih (solver puzzle = hitam)."""
    fields = fen.split()
    return len(fields) >= 2 and fields[1] == "w"


def attack_theme_labels(themes: Sequence[str] | None) -> set[str]:
    """Ambil hanya theme motif serangan dari daftar ``Themes``."""
    return set(themes or ()) & ATTACK_THEMES


def attack_label_vector(themes: Sequence[str] | None) -> list[int]:
    """Vektor 0/1 multi-label sesuai urutan :data:`ATTACK_CLASSES`."""
    present = attack_theme_labels(themes)
    return [int(name in present) for name in ATTACK_CLASSES]


def attack_label_matrix(themes_rows: Sequence[Sequence[str] | None]) -> np.ndarray:
    """Matriks label ``(n_baris, n_kelas)`` bertipe ``int8``.

    ``Themes`` di dataset bisa ``None``; baris seperti itu jadi semua nol (tapi
    loader sudah membuangnya lewat :func:`is_black_attack_row`).
    """
    return np.asarray(
        [attack_label_vector(themes) for themes in themes_rows], dtype=np.int8
    )


def split_by_game_id(
    game_ids: Sequence[str],
    test_size: float = 0.2,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """Bagi indeks train/test per ``GameId`` agar tidak ada game yang bocor.

    FEN yang sama bisa muncul di beberapa puzzle dari game yang sama; split per
    baris akan menaruh duplikat di dua sisi. Mengembalikan ``(mask_train,
    mask_test)`` berupa array boolean sepanjang ``game_ids``.
    """
    ids = np.asarray(game_ids)
    unique_ids = np.unique(ids)
    rng = np.random.default_rng(seed)
    rng.shuffle(unique_ids)
    n_test = max(1, int(len(unique_ids) * test_size)) if len(unique_ids) > 1 else 0
    test_ids = set(unique_ids[:n_test].tolist())
    mask_test = np.fromiter((gid in test_ids for gid in ids), dtype=bool, count=len(ids))
    return ~mask_test, mask_test


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
