"""Siapkan subset Lichess untuk model pola serangan hitam.

Jalankan dari folder ``backend/``:

    uv run python prepare_black_attack.py --limit 200000
    uv run python prepare_black_attack.py --limit 0 --output datasets/black_attack

``--limit 0`` memuat semua baris hasil filter (sekitar 2 juta).
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from app.tactical import (
    ATTACK_THEMES,
    DATASET_ID,
    attack_theme_labels,
    load_black_attack_dataset,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Siapkan dataset serangan hitam dari Lichess.")
    parser.add_argument(
        "--limit",
        type=int,
        default=200_000,
        help="Batas baris setelah filter (0 = semua). Default 200000.",
    )
    parser.add_argument(
        "--min-popularity",
        type=int,
        default=50,
        help="Buang puzzle dengan Popularity di bawah nilai ini. Default 50.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Opsional: simpan Dataset hasil filter ke folder ini.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    limit = None if args.limit == 0 else args.limit

    print(f"Memuat {DATASET_ID} dari HuggingFace ...")
    dataset = load_black_attack_dataset(
        min_popularity=args.min_popularity,
        limit=limit,
        seed=args.seed,
    )
    print(f"  baris setelah filter : {len(dataset):,}")
    print(f"  kolom                : {dataset.column_names}")

    theme_counts: Counter[str] = Counter()
    for themes in dataset["Themes"]:
        theme_counts.update(attack_theme_labels(themes))
    print("  motif teratas        :")
    for theme, count in theme_counts.most_common(10):
        print(f"    {theme:<20} {count:,}")

    free_themes = sorted(ATTACK_THEMES - set(theme_counts))
    if free_themes:
        print(f"  motif tanpa contoh   : {', '.join(free_themes)}")

    print("\nContoh baris:")
    print(dataset[0])

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        dataset.save_to_disk(str(args.output))
        print(f"\nDataset disimpan ke: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
