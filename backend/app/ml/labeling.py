"""Definisi label fase permainan.

Label mengikuti kolom ``phase`` pada dataset. Tidak ada heuristik buatan
sendiri di sini supaya tidak menimbulkan sirkularitas label.
"""

from __future__ import annotations

PHASES: tuple[str, ...] = ("opening", "middlegame", "endgame")
PHASE_SET: frozenset[str] = frozenset(PHASES)


def normalize_phase(value: str) -> str:
    """Normalisasi label mentah menjadi salah satu anggota :data:`PHASES`."""
    label = str(value).strip().lower()
    if label not in PHASE_SET:
        raise ValueError(f"label fase tidak dikenal: {value!r}")
    return label
