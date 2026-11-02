"""Test filter dataset taktis (tanpa unduh dataset dari HuggingFace)."""

from __future__ import annotations

from app.tactical import (
    ATTACK_THEMES,
    attack_theme_labels,
    fen_white_to_move,
    is_black_attack_row,
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
