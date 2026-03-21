"""Tests for abstract food market extraction (get_market_food_df)."""

import pandas as pd

from analysis.savegame.loader import (
    SaveAdapter,
    _row_from_market_entry_no_goods,
    get_market_food_df,
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
