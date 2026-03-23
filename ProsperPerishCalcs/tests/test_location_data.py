import pytest

import pandas as pd

from core.parser.path_resolver import PathResolver
from core.data.location_data import LocationData
from analysis.building_levels.building_analysis.utils import load_config


@pytest.fixture(scope="module")
def location_data():
    """Load location data once for the whole module. Shared by all tests."""
    config = load_config()
    path_resolver = PathResolver(config["game_path"], config["mod_path"])
    data = LocationData(path_resolver)
    data.load_all()
    data.get_merged_df()  # Warm cache so get_location_by_tag and merged_df use it
    return data


@pytest.fixture(scope="module")
def merged_df(location_data):
    """Cached merged DataFrame. Computed once in location_data, shared by all tests that need it."""
    return location_data.modded_df


def test_owner_tag_column_present(merged_df):
    """owner_tag column exists in merged DataFrame."""
    assert "owner_tag" in merged_df.columns


def test_owner_tag_owned_locations(merged_df):
    """Known vanilla locations have correct owner tags at game start."""
    df = merged_df
    owned = df[df["owner_tag"].notna()]

    stockholm = owned[owned["location"] == "stockholm"]
    assert len(stockholm) == 1
    assert stockholm.iloc[0]["owner_tag"] == "SWE"

    # At least one location per known country
    tags = owned["owner_tag"].unique()
    assert "SWE" in tags


def test_owner_tag_unowned_locations(merged_df):
    """Unowned locations (seazones, lakes, uncolonized) have NA owner_tag."""
    unowned = merged_df[merged_df["owner_tag"].isna()]
    assert len(unowned) > 0


def test_owner_tag_coverage(merged_df):
    """Some locations are owned, some are not."""
    owned_count = merged_df["owner_tag"].notna().sum()
    unowned_count = merged_df["owner_tag"].isna().sum()
    assert owned_count > 0
    assert unowned_count > 0


def test_get_location_by_tag(location_data):
    """get_location_by_tag returns correct row for valid location tag."""
    stockholm = location_data.get_location_by_tag("stockholm")
    assert stockholm is not None
    assert stockholm["location"] == "stockholm"


def test_stockholm_location_rank_town(location_data):
    """Stockholm should be a town at game start (from 07_cities_and_buildings)."""
    stockholm = location_data.get_location_by_tag("stockholm")
    assert stockholm is not None
    assert stockholm["location_rank"] == "town"
    assert stockholm["town_setup"] == "important_scandinavian_town"


def test_victuals_market_columns_present(merged_df):
    """victuals_market_amount, food_victuals_market, total_food_production exist and are consistent."""
    df = merged_df
    assert "victuals_market_amount" in df.columns
    assert "food_victuals_market" in df.columns
    assert "total_food_production" in df.columns
    diff = (df["total_food_production"] - df["food_subsistence"] - df["food_victuals_market"]).abs()
    assert (diff < 0.001).all(), "total_food_production should equal food_subsistence + food_victuals_market"


def test_stockholm_has_victuals_market(location_data):
    """Stockholm (SWE capital) gets victuals_market from pp_game_start."""
    stockholm = location_data.get_location_by_tag("stockholm")
    assert stockholm is not None
    assert stockholm["victuals_market_amount"] >= 1
    assert stockholm["food_victuals_market"] > 0


def test_is_ownable_column_present(merged_df):
    """is_ownable column exists and is boolean True/False."""
    assert "is_ownable" in merged_df.columns
    assert merged_df["is_ownable"].dtype == bool


def test_is_ownable_known_ownable(location_data):
    """Known ownable land locations have is_ownable=True."""
    stockholm = location_data.get_location_by_tag("stockholm")
    assert stockholm is not None
    assert stockholm["is_ownable"] == True  # use == for numpy/pandas bool


def test_is_ownable_some_false(merged_df):
    """Some locations (corridors, sea) have is_ownable=False."""
    non_ownable = merged_df[~merged_df["is_ownable"]]
    assert len(non_ownable) > 0


def test_is_ownable_counts_match_base(location_data, merged_df):
    """Base location count (hierarchy, before transformations) equals is_ownable True + is_ownable False."""
    base_locations = {e["location"] for e in location_data.hierarchy_list if "location" in e}
    base_count = len(base_locations)

    n_true = (merged_df["is_ownable"] == True).sum()
    n_false = (merged_df["is_ownable"] == False).sum()

    assert base_count == n_true + n_false, (
        f"Base locations {base_count} != is_ownable True ({n_true}) + False ({n_false})"
    )


def test_population_capacity_column_present(merged_df):
    """population_capacity column exists and has non-negative values."""
    assert "population_capacity" in merged_df.columns
    assert (merged_df["population_capacity"] >= 0).all()


def test_population_capacity_stockholm_positive(location_data):
    """Stockholm has positive population capacity from topography, vegetation, climate, development."""
    stockholm = location_data.get_location_by_tag("stockholm")
    assert stockholm is not None
    assert stockholm["population_capacity"] > 0
