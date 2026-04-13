"""Wide I/O matrix for buildings x production methods (merged game + mod data)."""

import pytest

from core.parser.path_resolver import PathResolver
from core.data.building_data import BuildingData
from core.data.goods_data import GoodsData
from core.data.building_pm_io import build_pm_io_matrix, iter_production_methods_for_building
from analysis.building_levels.building_analysis.utils import load_config


@pytest.fixture
def building_and_goods():
    config = load_config()
    path_resolver = PathResolver(config["game_path"], config["mod_path"])
    building_data = BuildingData(path_resolver)
    goods_data = GoodsData(path_resolver)
    building_data.load_all()
    goods_data.load_all()
    return building_data, goods_data


def test_iter_dedupes_building_pm_pair(building_and_goods):
    building_data, _ = building_and_goods
    b = building_data.get_building("cloth_guild")
    pairs = list(
        iter_production_methods_for_building("cloth_guild", b, building_data)
    )
    names = [p[0] for p in pairs]
    assert len(names) == len(set(names))


def test_matrix_cloth_guild_cotton_row(building_and_goods):
    building_data, goods_data = building_and_goods
    df = build_pm_io_matrix(building_data, goods_data, merged=True)
    assert "max_levels" in df.columns
    sub = df[
        (df["building"] == "cloth_guild")
        & (df["production_method"] == "cotton_cloth_guild_maintenance")
    ]
    assert len(sub) == 1
    assert sub["max_levels"].iloc[0] == "guild_max_level"
    assert sub["i_cotton"].iloc[0] == pytest.approx(0.8)
    assert sub["o_cloth"].iloc[0] == pytest.approx(1.0)


def test_matrix_every_row_has_positive_output(building_and_goods):
    building_data, goods_data = building_and_goods
    df = build_pm_io_matrix(building_data, goods_data, merged=True)
    assert len(df) > 0
    o_cols = [c for c in df.columns if c.startswith("o_")]
    sums = df[o_cols].sum(axis=1)
    assert (sums > 0).all()


def test_matrix_no_debug_max_profit_input_columns(building_and_goods):
    building_data, goods_data = building_and_goods
    df = build_pm_io_matrix(building_data, goods_data, merged=True)
    i_cols = [c for c in df.columns if c.startswith("i_")]
    assert "i_debug_max_profit" not in i_cols


def test_matrix_victuals_output_when_mod_defines_cookery(building_and_goods):
    building_data, goods_data = building_and_goods
    if "victuals" not in goods_data.modded_df.index:
        pytest.skip("mod does not define victuals good")
    if "cookery" not in building_data.modded_df.index:
        pytest.skip("mod does not define cookery building")
    df = build_pm_io_matrix(building_data, goods_data, merged=True)
    sub = df[(df["building"] == "cookery") & (df["o_victuals"] > 0)]
    assert len(sub) >= 1


def test_vanilla_matrix_cloth_guild(building_and_goods):
    building_data, goods_data = building_and_goods
    df = build_pm_io_matrix(building_data, goods_data, merged=False)
    sub = df[
        (df["building"] == "cloth_guild")
        & (df["production_method"] == "cotton_cloth_guild_maintenance")
    ]
    assert len(sub) == 1
    assert sub["i_cotton"].iloc[0] == pytest.approx(0.8)
    assert sub["o_cloth"].iloc[0] == pytest.approx(1.0)


def test_vanilla_matrix_fewer_columns_than_merged_when_mod_adds_goods(building_and_goods):
    building_data, goods_data = building_and_goods
    merged_df = build_pm_io_matrix(building_data, goods_data, merged=True)
    vanilla_df = build_pm_io_matrix(building_data, goods_data, merged=False)
    assert len(vanilla_df.columns) <= len(merged_df.columns)
