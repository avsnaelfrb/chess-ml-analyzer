"""Training model taktis multi-label untuk pola serangan hitam.

Alur:
    dataset Lichess (FEN giliran putih) -> label Themes -> fitur taktis
    -> split per GameId -> One-vs-Rest LogisticRegression -> artifact joblib

Jalankan dari folder ``backend/``:

    uv run python train_black_attack.py                  # sampel 200k
    uv run python train_black_attack.py --sample 0       # seluruh data

Evaluasi memakai per-kelas average precision (AP) dan macro-F1, bukan accuracy,
karena distribusi motif sangat timpang (``mate`` ~44%, ``interference`` ~0,5%).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, f1_score
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .config import (
    BLACK_ATTACK_METRICS_PATH,
    BLACK_ATTACK_MODEL_PATH,
    BLACK_ATTACK_MODEL_VERSION,
)
from .tactical import (
    ATTACK_CLASSES,
    DATASET_ID,
    attack_label_matrix,
    load_black_attack_dataset,
    split_by_game_id,
)
from .tactical_features import FEATURE_NAMES, TacticalFeatureExtractor


def build_pipeline(seed: int = 42, max_iter: int = 500) -> Pipeline:
    """Pipeline: FEN -> fitur taktis -> standardisasi -> One-vs-Rest LR."""
    return Pipeline(
        steps=[
            ("features", TacticalFeatureExtractor()),
            ("scale", StandardScaler()),
            (
                "clf",
                OneVsRestClassifier(
                    LogisticRegression(
                        max_iter=max_iter,
                        # Tanpa class_weight="balanced": bobot seimbang membuat
                        # motif langka overconfident di posisi di luar training.
                        solver="liblinear",
                        random_state=seed,
                    ),
                    n_jobs=-1,
                ),
            ),
        ]
    )


def evaluate_multilabel(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    classes: tuple[str, ...] = ATTACK_CLASSES,
    threshold: float = 0.5,
) -> dict:
    """Hitung AP per kelas + macro-F1, lewati kelas tanpa contoh positif."""
    y_pred = (y_proba >= threshold).astype(np.int8)
    per_class: dict[str, dict[str, float | int | None]] = {}
    aps: list[float] = []
    f1s: list[float] = []

    for index, name in enumerate(classes):
        support = int(y_true[:, index].sum())
        if support == 0:
            per_class[name] = {
                "support": 0,
                "average_precision": None,
                "f1": None,
            }
            continue

        ap = float(average_precision_score(y_true[:, index], y_proba[:, index]))
        f1 = float(f1_score(y_true[:, index], y_pred[:, index], zero_division=0))
        aps.append(ap)
        f1s.append(f1)
        per_class[name] = {
            "support": support,
            "average_precision": ap,
            "f1": f1,
        }

    return {
        "macro_average_precision": float(np.mean(aps)) if aps else 0.0,
        "macro_f1": float(np.mean(f1s)) if f1s else 0.0,
        "micro_f1": float(f1_score(y_true, y_pred, average="micro", zero_division=0)),
        "subset_accuracy": float((y_true == y_pred).all(axis=1).mean()),
        "threshold": threshold,
        "per_class": per_class,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Latih model multi-label pola serangan hitam dari Lichess."
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=200_000,
        help="Jumlah baris setelah filter (0 = semua). Default 200000.",
    )
    parser.add_argument(
        "--min-popularity",
        type=int,
        default=50,
        help="Buang puzzle dengan Popularity di bawah nilai ini. Default 50.",
    )
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-iter", type=int, default=500)
    parser.add_argument("--output", type=Path, default=BLACK_ATTACK_MODEL_PATH)
    parser.add_argument("--metrics", type=Path, default=BLACK_ATTACK_METRICS_PATH)
    return parser.parse_args(argv)


def _print_report(metrics: dict) -> None:
    print("  evaluasi per motif:")
    rows = sorted(
        metrics["per_class"].items(),
        key=lambda item: int(item[1]["support"] or 0),
        reverse=True,
    )
    for name, values in rows:
        ap = values["average_precision"]
        f1 = values["f1"]
        ap_text = f"{ap:.3f}" if ap is not None else "  -  "
        f1_text = f"{f1:.3f}" if f1 is not None else "  -  "
        print(f"    {name:<22} n={values['support']:>7,}  AP={ap_text}  F1={f1_text}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    limit = None if args.sample == 0 else args.sample

    print(f"Memuat {DATASET_ID} (limit={limit or 'semua'}) ...")
    dataset = load_black_attack_dataset(
        min_popularity=args.min_popularity,
        limit=limit,
        seed=args.seed,
    )
    print(f"  baris                : {len(dataset):,}")
    if len(dataset) < 100:
        print("[ERROR] Data terlalu sedikit untuk training.")
        return 1

    fens = list(dataset["FEN"])
    labels = attack_label_matrix(dataset["Themes"])
    train_mask, test_mask = split_by_game_id(
        dataset["GameId"], test_size=args.test_size, seed=args.seed
    )
    train_idx = np.flatnonzero(train_mask)
    test_idx = np.flatnonzero(test_mask)
    print(f"  split by GameId      : train={len(train_idx):,} test={len(test_idx):,}")
    if len(train_idx) == 0 or len(test_idx) == 0:
        print("[ERROR] Split kosong; tambah sampel atau ubah --test-size.")
        return 1

    pipeline = build_pipeline(seed=args.seed, max_iter=args.max_iter)
    pipeline.fit([fens[i] for i in train_idx], labels[train_idx])
    probabilities = pipeline.predict_proba([fens[i] for i in test_idx])

    metrics = evaluate_multilabel(labels[test_idx], probabilities)
    metrics.update(
        {
            "model_version": BLACK_ATTACK_MODEL_VERSION,
            "dataset": DATASET_ID,
            "rows": len(dataset),
            "train_size": len(train_idx),
            "test_size": len(test_idx),
            "sample": args.sample,
            "min_popularity": args.min_popularity,
            "seed": args.seed,
            "classes": list(ATTACK_CLASSES),
            "feature_count": len(FEATURE_NAMES),
        }
    )
    print(
        "  macro AP             : "
        f"{metrics['macro_average_precision']:.4f}"
    )
    print(f"  macro F1             : {metrics['macro_f1']:.4f}")
    print(f"  micro F1             : {metrics['micro_f1']:.4f}")
    print(f"  subset accuracy      : {metrics['subset_accuracy']:.4f}")
    _print_report(metrics)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "pipeline": pipeline,
            "classes": ATTACK_CLASSES,
            "feature_names": FEATURE_NAMES,
            "model_version": BLACK_ATTACK_MODEL_VERSION,
        },
        args.output,
    )
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    args.metrics.write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"\nArtifact : {args.output}")
    print(f"Metrik   : {args.metrics}")
    return 0
