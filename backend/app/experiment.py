"""Eksperimen: bandingkan set fitur & algoritma untuk klasifikasi fase.

Bukan bagian dari kontrak produksi. Tujuannya menjawab:
  - apakah fitur non-ply (murni posisi) mengubah perilaku model?
  - apakah algoritma lain mengubah hasil?

Jalankan dari folder backend/:

    uv run python -m app.experiment --sample 80000
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .config import DATASET_PATH
from .ml import (
    FEN_COLUMN,
    FEATURE_NAMES,
    GROUP_COLUMN,
    LABEL_COLUMN,
    extract_features,
    is_valid_fen,
    load_frame,
    normalize_phase,
)

PLY_FEATURES = ("ply", "fullmove_number", "halfmove_clock")
TURN_FEATURES = ("side_to_move_white", "castling_rights", "has_en_passant")

# Posisi probe: laporan label tiap varian pada kasus yang "menyakitkan".
PROBES = {
    "start": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "scholars_mate(ply4)": "r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4",
    "fools_mate(ply3)": "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3",
    "K+Q mate(fullmove1)": "7k/6Q1/5K2/8/8/8/8/8 b - - 0 1",
    "K+R mate(fullmove1)": "R6k/8/6K1/8/8/8/8/8 b - - 0 1",
    "real_endgame(ply80)": "8/5k2/8/4p3/8/4K3/4P3/8 w - - 0 41",
}


def build_feature_frame(fens: list[str]) -> pd.DataFrame:
    """Hitung semua fitur FEN sekali (bagian paling mahal)."""
    rows = [extract_features(f) for f in fens]
    frame = pd.DataFrame(rows)
    # Fitur turunan "posisi murni": seberapa jauh papan dari posisi awal.
    frame["nonpawn_material_total"] = frame["material_total"] - frame["pawn_count_total"]
    frame["material_fraction"] = frame["material_total"] / 78.0
    frame["queen_count_total"] = frame["white_queen"] + frame["black_queen"]
    frame["has_queens"] = (frame["queen_count_total"] > 0).astype(float)
    return frame


def feature_sets(frame: pd.DataFrame) -> dict[str, list[str]]:
    all_names = list(FEATURE_NAMES)
    derived = [
        "nonpawn_material_total",
        "material_fraction",
        "queen_count_total",
        "has_queens",
    ]
    no_ply = [n for n in all_names if n not in PLY_FEATURES]
    no_ply_no_turn = [n for n in no_ply if n not in TURN_FEATURES]
    return {
        "baseline": all_names,
        "no_ply": no_ply,
        "no_ply_no_turn": no_ply_no_turn,
        "positional(+derived)": all_names + derived,
        "no_ply+derived": no_ply + derived,
    }


def make_model(kind: str, seed: int, trees: int) -> Pipeline:
    if kind == "rf":
        clf = RandomForestClassifier(
            n_estimators=trees, random_state=seed, n_jobs=-1
        )
    elif kind == "hgb":
        clf = HistGradientBoostingClassifier(random_state=seed)
    elif kind == "logreg":
        clf = LogisticRegression(max_iter=1000, n_jobs=-1)
        return Pipeline([("scale", StandardScaler()), ("clf", clf)])
    else:  # pragma: no cover
        raise ValueError(kind)
    return Pipeline([("clf", clf)])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=type(DATASET_PATH), default=DATASET_PATH)
    parser.add_argument("--sample", type=int, default=80_000)
    parser.add_argument("--trees", type=int, default=150)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    print(f"Memuat sampel {args.sample:,} baris ...")
    df = load_frame(args.dataset, limit=args.sample, seed=args.seed)
    df = df.dropna(subset=[FEN_COLUMN, LABEL_COLUMN, GROUP_COLUMN]).copy()
    df[LABEL_COLUMN] = df[LABEL_COLUMN].map(normalize_phase)
    df = df[df[FEN_COLUMN].map(is_valid_fen)].reset_index(drop=True)
    print(f"  baris siap           : {len(df):,}")

    fens = df[FEN_COLUMN].tolist()
    print("Menghitung fitur FEN (python-chess) ...")
    features = build_feature_frame(fens)

    y = df[LABEL_COLUMN].to_numpy()
    groups = df[GROUP_COLUMN].to_numpy()
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=args.seed)
    train_idx, test_idx = next(splitter.split(fens, y, groups))

    probe_frame = build_feature_frame(list(PROBES.values()))

    results: list[dict] = []

    def run(tag: str, names: list[str], kind: str) -> None:
        model = make_model(kind, args.seed, args.trees)
        model.fit(features.iloc[train_idx][names], y[train_idx])
        pred = model.predict(features.iloc[test_idx][names])
        acc = accuracy_score(y[test_idx], pred)

        # Akurasi dedup FEN (selaras secara posisional dengan baris test).
        test_fens = np.asarray(fens)[test_idx]
        keep = ~pd.Series(test_fens).duplicated().to_numpy()
        dedup_feats = features.iloc[test_idx][names].loc[keep]
        dedup_y = y[test_idx][keep]
        dedup_pred = model.predict(dedup_feats)
        dedup_acc = accuracy_score(dedup_y, dedup_pred)

        probe_pred = model.predict(probe_frame[names])
        results.append(
            {
                "tag": tag,
                "kind": kind,
                "n_features": len(names),
                "accuracy": round(float(acc), 4),
                "dedup_accuracy": round(float(dedup_acc), 4),
                "probes": dict(zip(PROBES.keys(), probe_pred.tolist())),
            }
        )
        print(f"  {tag:<26} {kind:<7} acc={acc:.4f} dedup={dedup_acc:.4f}")

    print("\n== Perbandingan set fitur (RandomForest) ==")
    for tag, names in feature_sets(features).items():
        run(tag, names, "rf")

    print("\n== Perbandingan algoritma (fitur baseline) ==")
    for kind in ("rf", "hgb", "logreg"):
        run("baseline", list(FEATURE_NAMES), kind)

    print("\n== Label pada posisi probe ==")
    header = f"{'probe':<22}" + "".join(f"{r['kind']}:{r['tag'][:12]:<12}" for r in results)
    print(header)
    for probe in PROBES:
        row = f"{probe:<22}"
        for r in results:
            row += f"{r['probes'][probe]:<17}"
        print(row)

    print("\n== Rangkuman ==")
    for r in results:
        print(
            f"{r['tag']:<22} {r['kind']:<7} feats={r['n_features']:<3} "
            f"acc={r['accuracy']} dedup={r['dedup_accuracy']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())