"""Tests for analysis.building_levels.scripts.generate_rgo_startup_buildings."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from analysis.building_levels.scripts.generate_rgo_startup_buildings import (
    iter_effects,
    load_rgo_sheet,
    parse_yes,
    render_game_start_snippet,
)


REQUIRED = [
    "good",
    "n_pm_outputs",
    "building_set",
    "minimum_population",
    "minimum_development",
    "rural",
    "town",
    "city",
    "startup",
    "amount_buil",
]


def _write_fixture(path: Path, rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    for c in REQUIRED:
        if c not in df.columns:
            df[c] = None
    df = df[REQUIRED]
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="RGO_goods", index=False)


def test_parse_yes() -> None:
    assert parse_yes("yes") is True
    assert parse_yes("NO") is False
    assert parse_yes("1") is True
    assert parse_yes("") is None
    assert parse_yes(float("nan")) is None


def test_startup_and_empty_building_skip(tmp_path: Path) -> None:
    p = tmp_path / "t.xlsx"
    _write_fixture(
        p,
        [
            {
                "good": "wheat",
                "n_pm_outputs": 1,
                "building_set": "farming_village",
                "minimum_population": 100,
                "minimum_development": 0,
                "rural": "yes",
                "town": "no",
                "city": "no",
                "startup": "no",
                "amount_buil": 1,
            },
            {
                "good": "rice",
                "n_pm_outputs": 1,
                "building_set": "",
                "minimum_population": 100,
                "minimum_development": 0,
                "rural": "yes",
                "town": "no",
                "city": "no",
                "startup": "yes",
                "amount_buil": 1,
            },
            {
                "good": "fish",
                "n_pm_outputs": 1,
                "building_set": "fishing_village",
                "minimum_population": 50,
                "minimum_development": 0,
                "rural": "yes",
                "town": "no",
                "city": "no",
                "startup": "yes",
                "amount_buil": 1,
            },
        ],
    )
    df = load_rgo_sheet(p, "RGO_goods")
    effects = iter_effects(df)
    assert len(effects) == 1
    assert effects[0]["good"] == "fish"
    assert effects[0]["building"] == "fishing_village"
    assert effects[0]["use_dev"] is False


def test_dev_gate_when_positive(tmp_path: Path) -> None:
    p = tmp_path / "t.xlsx"
    _write_fixture(
        p,
        [
            {
                "good": "clay",
                "n_pm_outputs": 1,
                "building_set": "test_workshop",
                "minimum_population": 10,
                "minimum_development": 25,
                "rural": "no",
                "town": "yes",
                "city": "no",
                "startup": "yes",
                "amount_buil": 1,
            },
        ],
    )
    df = load_rgo_sheet(p, "RGO_goods")
    effects = iter_effects(df)
    assert len(effects) == 1
    assert effects[0]["use_dev"] is True
    assert effects[0]["min_dev"] == 25
    text = render_game_start_snippet(effects, source_comment="test")
    assert "development > 25" in text
    assert "goods:clay" in text
    assert "location_rank:town" in text


def test_three_ranks(tmp_path: Path) -> None:
    p = tmp_path / "t.xlsx"
    _write_fixture(
        p,
        [
            {
                "good": "iron",
                "n_pm_outputs": 1,
                "building_set": "mining_village",
                "minimum_population": 1,
                "minimum_development": 0,
                "rural": "yes",
                "town": "yes",
                "city": "yes",
                "startup": "yes",
                "amount_buil": 1,
            },
        ],
    )
    df = load_rgo_sheet(p, "RGO_goods")
    effects = iter_effects(df)
    assert len(effects) == 3
    ranks = {e["rank_key"] for e in effects}
    assert ranks == {"rural_settlement", "town", "city"}


def test_sort_order_stable(tmp_path: Path) -> None:
    p = tmp_path / "t.xlsx"
    _write_fixture(
        p,
        [
            {
                "good": "zinc",
                "n_pm_outputs": 1,
                "building_set": "b1",
                "minimum_population": 0,
                "minimum_development": 0,
                "rural": "yes",
                "town": "no",
                "city": "no",
                "startup": "yes",
                "amount_buil": 1,
            },
            {
                "good": "amber",
                "n_pm_outputs": 1,
                "building_set": "b2",
                "minimum_population": 0,
                "minimum_development": 0,
                "rural": "yes",
                "town": "no",
                "city": "no",
                "startup": "yes",
                "amount_buil": 1,
            },
        ],
    )
    df = load_rgo_sheet(p, "RGO_goods")
    effects = iter_effects(df)
    assert [e["good"] for e in effects] == ["amber", "zinc"]


def test_amount_buil_adds_extra_levels(tmp_path: Path) -> None:
    p = tmp_path / "t.xlsx"
    _write_fixture(
        p,
        [
            {
                "good": "copper",
                "n_pm_outputs": 1,
                "building_set": "mining_village",
                "minimum_population": 1,
                "minimum_development": 0,
                "rural": "yes",
                "town": "no",
                "city": "no",
                "startup": "yes",
                "amount_buil": 4,
            },
        ],
    )
    df = load_rgo_sheet(p, "RGO_goods")
    effects = iter_effects(df)
    assert effects[0]["amount"] == 4
    text = render_game_start_snippet(effects, source_comment="test")
    assert text.count("if = {") == 2
    assert "change_building_level_in_location" in text
    assert "value < 4" in text
    assert "location_building_level(building_type:mining_village)" in text
    assert "multiply = -1" in text
    assert "construct_building" in text
