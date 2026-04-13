"""Tests for GoodsSubsets."""

import pandas as pd
import pytest

from core.data.goods_data import GoodsData
from core.data.goods_subsets import GoodsSubsets
from core.parser.path_resolver import PathResolver
from analysis.building_levels.building_analysis.utils import load_config


@pytest.fixture
def goods_data():
    config = load_config()
    path_resolver = PathResolver(config["game_path"], config["mod_path"])
    data = GoodsData(path_resolver)
    data.load_all()
    return data


def test_from_dataframe_empty():
    """Empty frame yields empty tuples and dict."""
    gs = GoodsSubsets.from_dataframe(pd.DataFrame())
    assert gs.all == ()
    assert gs.by_method == {}
    assert gs.farming == ()
    assert gs.rgo == ()
    assert gs.vanilla_food == ()


def test_from_dataframe_groups_by_method_and_food():
    """method buckets and with_food follow game-like columns."""
    df = pd.DataFrame(
        {
            "method": ["farming", "mining", "farming", "hunting"],
            "category": ["raw_material", "produced", "raw_material", "raw_material"],
            "food": [1.0, 0.0, 0.5, 0.0],
            "default_market_price": [1.0, 1.0, 1.0, 1.0],
            "transport_cost": [1.0, 1.0, 1.0, 1.0],
        },
        index=["wheat", "iron", "rice", "fur"],
    )
    gs = GoodsSubsets.from_dataframe(df)
    assert set(gs.all) == {"wheat", "iron", "rice", "fur"}
    assert set(gs.farming) == {"wheat", "rice"}
    assert gs.mining == ("iron",)
    assert gs.hunting == ("fur",)
    assert set(gs.rgo) == {"wheat", "rice", "fur"}
    assert gs.raw_material == gs.rgo
    assert set(gs.with_food) == {"wheat", "rice"}
    assert gs.vanilla_food == ()

    vanilla_only = pd.DataFrame(
        {
            "method": ["farming", "mining"],
            "food": [2.0, 0.0],
            "default_market_price": [1.0, 1.0],
            "transport_cost": [1.0, 1.0],
        },
        index=["wheat", "iron"],
    )
    gs2 = GoodsSubsets.from_dataframe(df, vanilla_df=vanilla_only)
    assert gs2.vanilla_food == ("wheat",)


def test_from_dataframe_requires_method_column():
    df = pd.DataFrame({"food": [1.0]}, index=["a"])
    with pytest.raises(ValueError, match="method"):
        GoodsSubsets.from_dataframe(df)


def test_from_goods_data_matches_vanilla_df(goods_data):
    """Integration: from_goods_data(merged=False) matches from_dataframe(vanilla_df, vanilla_df=…)."""
    expected = GoodsSubsets.from_dataframe(
        goods_data.vanilla_df, vanilla_df=goods_data.vanilla_df
    )
    got = GoodsSubsets.from_goods_data(goods_data, merged=False)
    assert got == expected
    assert len(got.all) == 74
    assert len(got.rgo) == 52
    assert "cloth" not in got.rgo
    assert "wheat" in got.rgo
    assert "wheat" in got.farming
    assert "iron" in got.mining


def test_from_goods_data_merged_includes_all_slugs(goods_data):
    """Merged df is a superset of vanilla for good indices."""
    merged = GoodsSubsets.from_goods_data(goods_data, merged=True)
    vanilla = GoodsSubsets.from_goods_data(goods_data, merged=False)
    assert set(vanilla.all).issubset(set(merged.all))


def test_vanilla_food_always_from_vanilla_df(goods_data):
    """vanilla_food uses parsed vanilla gospel even when primary frame is modded_df."""
    merged = GoodsSubsets.from_goods_data(goods_data, merged=True)
    vanilla = GoodsSubsets.from_goods_data(goods_data, merged=False)
    assert merged.vanilla_food == vanilla.vanilla_food
    assert merged.vanilla_food == vanilla.with_food
