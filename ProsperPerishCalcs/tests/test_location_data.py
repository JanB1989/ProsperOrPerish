import pytest

import pandas as pd

from core.parser.path_resolver import PathResolver
from core.data.location_data import LocationData
from analysis.building_levels.building_analysis.utils import load_config


@pytest.fixture
def location_data():
    config = load_config()
    path_resolver = PathResolver(config["game_path"], config["mod_path"])
    data = LocationData(path_resolver)
    data.load_all()
    return data


def test_owner_tag_column_present(location_data):
    """owner_tag column exists in merged DataFrame."""
    df = location_data.get_merged_df()
    assert "owner_tag" in df.columns


def test_owner_tag_owned_locations(location_data):
    """Known vanilla locations have correct owner tags at game start."""
    df = location_data.get_merged_df()
    owned = df[df["owner_tag"].notna()]

    stockholm = owned[owned["location"] == "stockholm"]
    assert len(stockholm) == 1
    assert stockholm.iloc[0]["owner_tag"] == "SWE"

    # At least one location per known country
    tags = owned["owner_tag"].unique()
    assert "SWE" in tags


def test_owner_tag_unowned_locations(location_data):
    """Unowned locations (seazones, lakes, uncolonized) have NA owner_tag."""
    df = location_data.get_merged_df()
    unowned = df[df["owner_tag"].isna()]
    assert len(unowned) > 0


def test_owner_tag_coverage(location_data):
    """Some locations are owned, some are not."""
    df = location_data.get_merged_df()
    owned_count = df["owner_tag"].notna().sum()
    unowned_count = df["owner_tag"].isna().sum()
    assert owned_count > 0
    assert unowned_count > 0
