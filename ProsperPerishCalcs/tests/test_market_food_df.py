"""Tests for abstract food market extraction (get_market_food_df)."""

import pandas as pd

from analysis.savegame.loader import (
    MARKET_FOOD_CORE_COLUMNS,
    SaveAdapter,
    _row_from_market_entry_no_goods,
    get_market_food_df,
    select_market_food_core,
)


def test_row_skips_goods_and_renames_max() -> None:
    mm_entry = {
        "center": 1,
        "food": 100.0,
        "max": 500.0,
        "price": 0.5,
        "goods": {"wheat": {"price": 2.0}},
    }
    out = _row_from_market_entry_no_goods(mm_entry)
    assert "goods" not in out
    assert out["food"] == 100.0
    assert out["food_max"] == 500.0
    assert "max" not in out
    assert out["price"] == 0.5


def test_row_flattens_impacts() -> None:
    mm_entry = {
        "food": 1.0,
        "max": 2.0,
        "impacts": {"infantry_construction": -0.1},
        "goods": {},
    }
    out = _row_from_market_entry_no_goods(mm_entry)
    assert out["impacts_infantry_construction"] == -0.1
    assert out["food_max"] == 2.0


def test_get_market_food_df_save_adapter() -> None:
    data = {
        "metadata": {"date": "1400.1.1", "compatibility": {"locations": ["test_center"]}},
        "market_manager": {
            "database": {
                "10": {
                    "center": 1,
                    "food": 100.0,
                    "max": 500.0,
                    "price": 0.5,
                    "food_consumption": -1.0,
                    "goods": {"wheat": {"price": 2.0, "stockpile": 1.0}},
                }
            }
        },
        "locations": {"locations": {"1": {"name": "Test"}}},
    }
    save = SaveAdapter(data)
    df = get_market_food_df(save)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    row = df.iloc[0]
    assert int(row["market_id"]) == 10
    assert row["food"] == 100.0
    assert row["food_max"] == 500.0
    assert row["price"] == 0.5
    assert row["food_consumption"] == -1.0
    assert row["market_center_slug"] == "test_center"
    assert "wheat" not in df.columns


def test_select_market_food_core_subset_and_order() -> None:
    df = pd.DataFrame(
        {
            "market_id": [10],
            "market_center_slug": ["x"],
            "food": [1.0],
            "food_max": [2.0],
            "price": [0.5],
            "impacts_foo": [0.1],
        }
    )
    out = select_market_food_core(df)
    assert list(out.columns) == [
        "market_id",
        "market_center_slug",
        "food",
        "food_max",
        "price",
    ]
    assert "impacts_foo" not in out.columns


def test_select_market_food_core_with_snapshot() -> None:
    df = pd.DataFrame(
        {
            "snapshot": ["a"],
            "market_id": [1],
            "food": [1.0],
            "price": [0.1],
        }
    )
    out = select_market_food_core(df)
    assert list(out.columns) == ["snapshot", "market_id", "food", "price"]


def test_select_market_food_core_empty() -> None:
    empty = pd.DataFrame()
    assert select_market_food_core(empty).empty


def test_market_food_core_columns_tuple() -> None:
    assert "food" in MARKET_FOOD_CORE_COLUMNS
    assert "food_max" in MARKET_FOOD_CORE_COLUMNS
    assert "snapshot" not in MARKET_FOOD_CORE_COLUMNS
