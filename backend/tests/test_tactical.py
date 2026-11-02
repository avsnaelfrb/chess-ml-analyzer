"""Test filter dataset taktis (tanpa unduh dataset dari HuggingFace)."""

from __future__ import annotations

from app.tactical import (
    ATTACK_CLASSES,
    ATTACK_THEMES,
    attack_label_matrix,
    attack_label_vector,
    attack_theme_labels,
    fen_white_to_move,
    is_black_attack_row,
    split_by_game_id,
)

BLACK_ATTACK_ROW = {
    "FEN": "6k1/5p1p/4p3/4q3/3nN3/2Q3P1/PP3P1P/6K1 w - - 2 37",
    "Themes": ["crushing", "endgame", "fork", "short"],
    "Popularity": 90,
}


def test_fen_white_to_move() -> None:
    assert fen_white_to_move("8/8/8/8/8/8/8/8 w - - 0 1") is True
    assert fen_white_to_move("8/8/8/8/8/8/8/8 b - - 0 1") is False
    assert fen_white_to_move("bukan fen") is False


def test_attack_theme_labels_keeps_only_motifs() -> None:
    assert attack_theme_labels(["fork", "endgame", "crushing", "pin"]) == {"fork", "pin"}
    assert attack_theme_labels(None) == set()


def test_attack_themes_excludes_generic_tags() -> None:
    assert ATTACK_THEMES.isdisjoint(
        {"opening", "middlegame", "endgame", "short", "long", "crushing", "advantage", "master"}
    )


def test_black_attack_row_accepted() -> None:
    assert is_black_attack_row(BLACK_ATTACK_ROW) is True


def test_black_attack_row_rejected_when_black_to_move() -> None:
    row = {**BLACK_ATTACK_ROW, "FEN": "6k1/5p1p/4p3/4q3/3nN3/2Q3P1/PP3P1P/6K1 b - - 2 37"}
    assert is_black_attack_row(row) is False


def test_black_attack_row_rejected_without_attack_theme() -> None:
    row = {**BLACK_ATTACK_ROW, "Themes": ["endgame", "short"]}
    assert is_black_attack_row(row) is False


def test_black_attack_row_rejected_when_unpopular() -> None:
    row = {**BLACK_ATTACK_ROW, "Popularity": 10}
    assert is_black_attack_row(row, min_popularity=50) is False


def test_attack_label_vector_follows_attack_classes_order() -> None:
    vector = attack_label_vector(["fork", "mate", "endgame"])
    assert len(vector) == len(ATTACK_CLASSES)
    assert vector == [int(name in {"fork", "mate"}) for name in ATTACK_CLASSES]


def test_attack_label_matrix_shape_and_none() -> None:
    matrix = attack_label_matrix([["fork"], None, ["pin", "sacrifice"]])
    assert matrix.shape == (3, len(ATTACK_CLASSES))
    assert matrix.dtype == "int8"
    assert matrix[1].sum() == 0
    assert matrix[0].sum() == 1
    assert matrix[2].sum() == 2


def test_split_by_game_id_keeps_games_on_one_side() -> None:
    game_ids = ["a", "a", "b", "b", "c", "c", "d", "d", "e", "e"]
    train_mask, test_mask = split_by_game_id(game_ids, test_size=0.4, seed=7)

    assert (train_mask | test_mask).all()
    assert not (train_mask & test_mask).any()

    train_ids = set(game_ids[i] for i in range(len(game_ids)) if train_mask[i])
    test_ids = set(game_ids[i] for i in range(len(game_ids)) if test_mask[i])
    assert train_ids.isdisjoint(test_ids)
