"""Script training model klasifikasi fase.

Contoh pemakaian:

    uv run python -m app.ml.train                       # sampel 200k, default
    uv run python -m app.ml.train --sample 0            # seluruh dataset
    uv run python -m app.ml.train --sample 500000 --trees 300

Output: ``models/model.joblib`` dan ``models/metrics.json``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    log_loss,
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline

from ..config import DATASET_PATH, METRICS_PATH, MODEL_PATH, MODEL_VERSION
from .dataset import FEN_COLUMN, GROUP_COLUMN, LABEL_COLUMN, load_frame
from .features import FEATURE_NAMES, FenFeatureExtractor, is_valid_fen
from .labeling import PHASES, normalize_phase


def build_pipeline(seed: int = 42, trees: int = 200) -> Pipeline:
    """Pipeline: FEN -> fitur -> RandomForest."""
    return Pipeline(
        steps=[
            ("features", FenFeatureExtractor()),
            (
                "clf",
                RandomForestClassifier(
                    n_estimators=trees,
                    random_state=seed,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Latih model fase permainan catur.")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument(
        "--sample",
        type=int,
        default=200_000,
        help="Jumlah baris sampel (0 = seluruh dataset). Default 200000.",
    )
    parser.add_argument("--test-size", type=float, default=0.2, help="Proporsi test per game.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--trees", type=int, default=200, help="Jumlah pohon RandomForest.")
    parser.add_argument("--output", type=Path, default=MODEL_PATH)
    parser.add_argument("--metrics", type=Path, default=METRICS_PATH)
    return parser.parse_args(argv)


def _safe_phase(value: object) -> str | None:
    try:
        return normalize_phase(str(value))
    except ValueError:
        return None


def prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Bersihkan frame: label valid + FEN valid."""
    frame = frame.dropna(subset=[FEN_COLUMN, LABEL_COLUMN, GROUP_COLUMN]).copy()
    frame[LABEL_COLUMN] = frame[LABEL_COLUMN].map(_safe_phase)
    frame = frame.dropna(subset=[LABEL_COLUMN])
    frame = frame[frame[FEN_COLUMN].map(is_valid_fen)].reset_index(drop=True)
    return frame


def evaluate(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: np.ndarray,
    proba_labels: list[str],
) -> dict:
    """Metrik evaluasi dasar.

    Args:
        proba_labels: urutan kelas pada kolom ``y_proba`` (dari model), wajib
            untuk ``log_loss``.
    """
    labels = list(PHASES)
    report = classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "log_loss": float(log_loss(y_true, y_proba, labels=proba_labels)),
        "confusion_matrix": cm.tolist(),
        "classification_report": report,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    dataset_path = Path(args.dataset)

    if not dataset_path.exists():
        print(f"[ERROR] Dataset tidak ditemukan: {dataset_path}")
        return 1

    limit = None if args.sample == 0 else args.sample
    print(f"Memuat dataset: {dataset_path} (limit={limit or 'semua'})")
    frame = load_frame(dataset_path, limit=limit, seed=args.seed)
    print(f"  baris termuat        : {len(frame):,}")

    frame = prepare_frame(frame)
    print(f"  baris siap training  : {len(frame):,}")

    if frame.empty:
        print("[ERROR] Tidak ada data valid untuk training.")
        return 1

    label_counts = frame[LABEL_COLUMN].value_counts()
    print("  distribusi label     : " + ", ".join(f"{k}={v:,}" for k, v in label_counts.items()))

    X = frame[FEN_COLUMN].to_numpy()
    y = frame[LABEL_COLUMN].to_numpy()
    groups = frame[GROUP_COLUMN].to_numpy()

    splitter = GroupShuffleSplit(n_splits=1, test_size=args.test_size, random_state=args.seed)
    train_idx, test_idx = next(splitter.split(X, y, groups))
    print(
        f"  split by game        : train={len(train_idx):,} "
        f"({len(np.unique(groups[train_idx])):,} game), "
        f"test={len(test_idx):,} ({len(np.unique(groups[test_idx])):,} game)"
    )

    pipeline = build_pipeline(seed=args.seed, trees=args.trees)
    print(f"Training RandomForest({args.trees} pohon) ...")
    pipeline.fit(X[train_idx], y[train_idx])

    y_pred = pipeline.predict(X[test_idx])
    y_proba = pipeline.predict_proba(X[test_idx])
    metrics = evaluate(y[test_idx], y_pred, y_proba, list(pipeline.classes_))

    # Evaluasi versi dedup FEN (metrik lebih jujur terhadap posisi duplikat).
    test_frame = pd.DataFrame({FEN_COLUMN: X[test_idx], LABEL_COLUMN: y[test_idx]})
    dedup = test_frame.drop_duplicates(subset=[FEN_COLUMN])
    dedup_pred = pipeline.predict(dedup[FEN_COLUMN].to_numpy())
    dedup_acc = float(accuracy_score(dedup[LABEL_COLUMN], dedup_pred))
    metrics["dedup_accuracy"] = dedup_acc
    metrics["dedup_test_size"] = int(len(dedup))

    # Baseline: tebak kelas mayoritas di train.
    train_majority = pd.Series(y[train_idx]).mode()[0]
    baseline = float((y[test_idx] == train_majority).mean())
    metrics["baseline_majority"] = baseline
    metrics["majority_label"] = str(train_majority)

    # Fitur paling penting.
    importances = pipeline.named_steps["clf"].feature_importances_
    top_features = sorted(
        zip(FEATURE_NAMES, importances.tolist()), key=lambda item: item[1], reverse=True
    )[:10]
    metrics["top_features"] = [{"name": n, "importance": round(v, 5)} for n, v in top_features]

    metrics["model_version"] = MODEL_VERSION
    metrics["seed"] = args.seed
    metrics["trees"] = args.trees
    metrics["sample_limit"] = args.sample

    print("\n=== Hasil evaluasi (test = game yang belum pernah dilihat) ===")
    print(f"akurasi            : {metrics['accuracy']:.4f}")
    print(f"log_loss           : {metrics['log_loss']:.4f}")
    print(f"akurasi baseline   : {metrics['baseline_majority']:.4f} (tebak '{train_majority}')")
    print(f"akurasi dedup FEN  : {metrics['dedup_accuracy']:.4f} (n={metrics['dedup_test_size']:,})")
    print("\nclassification_report:")
    print(classification_report(y[test_idx], y_pred, labels=list(PHASES), zero_division=0))
    print("confusion_matrix (baris=true, kolom=pred, urutan " + "/".join(PHASES) + "):")
    print(np.asarray(metrics["confusion_matrix"]))
    print("\nTop fitur:")
    for item in metrics["top_features"]:
        print(f"  {item['name']:<22} {item['importance']:.5f}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    import joblib

    joblib.dump(pipeline, args.output)
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    args.metrics.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(f"\nModel disimpan : {args.output}")
    print(f"Metrik disimpan: {args.metrics}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
