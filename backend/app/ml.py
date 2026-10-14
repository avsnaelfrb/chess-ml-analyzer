"""Sisi ML: labeling, ekstraksi fitur, loader dataset, dan training jadi satu modul.

Alur data:
    FEN -> extract_features/fen_to_vector (fitur) -> GroupShuffleSplit -> pipeline -> model.joblib

Label fase mengikuti kolom ``phase`` dataset; tidak ada heuristik label buatan
sendiri (menghindari sirkularitas).

Training (dari folder backend/):
    uv run python train.py                       # sampel 200k, default
    uv run python train.py --sample 0            # seluruh dataset

Jangan jalankan `python -m app.ml`: kelas fitur akan ter-pickle di bawah
``__main__`` sehingga ``model.joblib`` gagal dimuat. Pakai ``train.py``.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator, Sequence
from pathlib import Path

import chess
import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    log_loss,
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline

from .config import DATASET_PATH, METRICS_PATH, MODEL_PATH, MODEL_VERSION

# ============================== Label fase ==============================

PHASES: tuple[str, ...] = ("opening", "middlegame", "endgame")
PHASE_SET: frozenset[str] = frozenset(PHASES)


def normalize_phase(value: str) -> str:
    """Normalisasi label mentah menjadi salah satu anggota :data:`PHASES`."""
    label = str(value).strip().lower()
    if label not in PHASE_SET:
        raise ValueError(f"label fase tidak dikenal: {value!r}")
    return label


# ============================== Ekstraksi fitur FEN ==============================
# Satu FEN -> satu vektor float dengan urutan tetap :data:`FEATURE_NAMES`.
# Modul ini dipakai training maupun serving lewat pipeline yang disimpan, sehingga
# mustahil terjadi drift fitur antara training dan prediksi.

# Nilai material (raja = 0, tidak dihitung sebagai material).
PIECE_VALUES: dict[int, int] = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}

# Urutan piece untuk nama fitur.
PIECE_ORDER: tuple[tuple[int, str], ...] = (
    (chess.PAWN, "pawn"),
    (chess.KNIGHT, "knight"),
    (chess.BISHOP, "bishop"),
    (chess.ROOK, "rook"),
    (chess.QUEEN, "queen"),
    (chess.KING, "king"),
)

COLOR_ORDER: tuple[tuple[bool, str], ...] = (
    (chess.WHITE, "white"),
    (chess.BLACK, "black"),
)


def _build_feature_names() -> tuple[str, ...]:
    names: list[str] = []
    for _, color in COLOR_ORDER:
        names += [
            f"material_{color}",
            f"piece_count_{color}",
            f"pawn_count_{color}",
        ]
        for _, piece in PIECE_ORDER:
            names.append(f"{color}_{piece}")
        names += [
            f"{color}_doubled_pawns",
            f"{color}_isolated_pawns",
            f"{color}_passed_pawns",
            f"{color}_pawn_islands",
        ]
    names += [
        "material_total",
        "piece_count_total",
        "pawn_count_total",
        "major_count_total",
        "minor_count_total",
        "side_to_move_white",
        "ply",
        "fullmove_number",
        "halfmove_clock",
        "castling_rights",
        "has_en_passant",
    ]
    return tuple(names)


FEATURE_NAMES: tuple[str, ...] = _build_feature_names()


def is_valid_fen(fen: str) -> bool:
    """Cek apakah FEN bisa diparse python-chess."""
    try:
        chess.Board(fen)
    except (ValueError, TypeError):
        return False
    return True


def pawn_structure_features(board: chess.Board) -> dict[str, float]:
    """Pola struktur pion per warna: dobel, terisolasi, passed, dan pulau pion.

    Ini bagian dari "pengenalan pola" strategis: posisi pion yang sama rapatnya
    tetap bisa berbeda fase/karakter permainan.

    Definisi:
    - ``doubled``: setiap pion "ekstra" di file yang sudah ditempati pion kawan.
    - ``isolated``: pion tanpa pion kawan di file bersebelahan (a/kanan).
    - ``passed``: tidak ada pion lawan di file sama/sejajar yang menghadang
      dari belakang menuju promosi.
    - ``pawn_islands``: jumlah kelompok file pion yang berurutan tanpa celah.
    """
    features: dict[str, float] = {}
    for color, color_name in COLOR_ORDER:
        pawns = board.pieces(chess.PAWN, color)
        enemy_pawns = board.pieces(chess.PAWN, not color)
        files = [chess.square_file(sq) for sq in pawns]
        file_set = set(files)

        doubled = sum(max(files.count(f) - 1, 0) for f in file_set)

        isolated = 0
        passed = 0
        for sq in pawns:
            f = chess.square_file(sq)
            r = chess.square_rank(sq)
            if not file_set.intersection((f - 1, f + 1)):
                isolated += 1
            if not any(
                chess.square_file(e) == d
                and (
                    chess.square_rank(e) > r
                    if color == chess.WHITE
                    else chess.square_rank(e) < r
                )
                for e in enemy_pawns
                for d in (f - 1, f, f + 1)
            ):
                passed += 1

        unique_sorted = sorted(file_set)
        islands = 1 if unique_sorted else 0
        for prev, cur in zip(unique_sorted, unique_sorted[1:]):
            if cur - prev > 1:
                islands += 1

        features[f"{color_name}_doubled_pawns"] = float(doubled)
        features[f"{color_name}_isolated_pawns"] = float(isolated)
        features[f"{color_name}_passed_pawns"] = float(passed)
        features[f"{color_name}_pawn_islands"] = float(islands)
    return features


def extract_features(fen: str) -> dict[str, float]:
    """Ubah satu FEN menjadi dictionary fitur.

    Raises:
        ValueError: bila FEN tidak valid.
    """
    try:
        board = chess.Board(fen)
    except (ValueError, TypeError) as exc:  # normalisasi pesan error
        raise ValueError(str(exc)) from exc

    features: dict[str, float] = {}

    material_total = 0
    piece_count_total = 0
    pawn_count_total = 0
    major_total = 0
    minor_total = 0

    for color, color_name in COLOR_ORDER:
        material = 0
        piece_count = 0
        pawn_count = 0
        for piece_type, piece_name in PIECE_ORDER:
            count = len(board.pieces(piece_type, color))
            features[f"{color_name}_{piece_name}"] = float(count)
            piece_count += count
            pawn_count += count if piece_type == chess.PAWN else 0
            material += count * PIECE_VALUES[piece_type]
            major_total += count if piece_type in (chess.ROOK, chess.QUEEN) else 0
            minor_total += count if piece_type in (chess.KNIGHT, chess.BISHOP) else 0
        features[f"material_{color_name}"] = float(material)
        features[f"piece_count_{color_name}"] = float(piece_count)
        features[f"pawn_count_{color_name}"] = float(pawn_count)
        material_total += material
        piece_count_total += piece_count
        pawn_count_total += pawn_count

    fullmove = int(board.fullmove_number)
    ply = (fullmove - 1) * 2 + (0 if board.turn == chess.WHITE else 1)

    features.update(pawn_structure_features(board))
    features["material_total"] = float(material_total)
    features["piece_count_total"] = float(piece_count_total)
    features["pawn_count_total"] = float(pawn_count_total)
    features["major_count_total"] = float(major_total)
    features["minor_count_total"] = float(minor_total)
    features["side_to_move_white"] = 1.0 if board.turn == chess.WHITE else 0.0
    features["ply"] = float(ply)
    features["fullmove_number"] = float(fullmove)
    features["halfmove_clock"] = float(board.halfmove_clock)
    features["castling_rights"] = float(bin(int(board.castling_rights)).count("1"))
    features["has_en_passant"] = 0.0 if board.ep_square is None else 1.0
    return features


def fen_to_vector(fen: str) -> list[float]:
    """Ubah satu FEN menjadi vektor float sesuai urutan :data:`FEATURE_NAMES`."""
    features = extract_features(fen)
    return [features[name] for name in FEATURE_NAMES]


class FenFeatureExtractor(BaseEstimator, TransformerMixin):
    """Transformer sklearn: iterable FEN -> matriks fitur.

    Dipasang sebagai langkah pertama pipeline supaya pipeline yang disimpan
    (``model.joblib``) sekaligus membawa logic ekstraksi fitur.
    """

    def fit(self, X: Sequence[str], y: object = None) -> "FenFeatureExtractor":
        return self

    def transform(self, X: Sequence[str]) -> np.ndarray:
        return np.asarray([fen_to_vector(fen) for fen in X], dtype=float)


# ============================== Loader dataset ==============================
# Dibaca streaming per-chunk supaya file besar (~500 MB) tidak masuk memori
# sekaligus. Hanya kolom yang dibutuhkan yang diambil.

# Hanya kolom yang dipakai; "ply" tidak dibaca karena diturunkan dari FEN.
REQUIRED_COLUMNS: tuple[str, ...] = ("game_id", "fen_before", "phase")
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


# ============================== Training ==============================

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

    # Tulis ke file sementara lalu ganti, agar artifact lama tidak rusak bila
    # proses berhenti di tengah penulisan.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp_model = args.output.with_name(args.output.name + ".tmp")
    joblib.dump(pipeline, tmp_model)
    tmp_model.replace(args.output)

    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    tmp_metrics = args.metrics.with_name(args.metrics.name + ".tmp")
    tmp_metrics.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    tmp_metrics.replace(args.metrics)

    print(f"\nModel disimpan : {args.output}")
    print(f"Metrik disimpan: {args.metrics}")
    return 0
