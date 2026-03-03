import pytest

import pandas as pd

from core.parser.path_resolver import PathResolver
from core.data.country_setup_data import CountrySetupData
from analysis.building_levels.building_analysis.utils import load_config


@pytest.fixture
def country_setup_data():
    config = load_config()
    path_resolver = PathResolver(config["game_path"], config["mod_path"])
    data = CountrySetupData(path_resolver)
    data.load_all()
    return data


def test_societal_values_df_columns(country_setup_data):
    """societal_values_df has owner_tag, spiritualist_vs_humanist, aristocracy_vs_plutocracy, capital."""
    df = country_setup_data.get_societal_values_df()
    assert "owner_tag" in df.columns
    assert "spiritualist_vs_humanist" in df.columns
    assert "aristocracy_vs_plutocracy" in df.columns
    assert "capital" in df.columns


def test_sweden_values(country_setup_data):
    """SWE has expected societal values and capital from setup."""
    df = country_setup_data.get_societal_values_df()
    swe = df[df["owner_tag"] == "SWE"].iloc[0]
    assert swe["spiritualist_vs_humanist"] == -50
    assert swe["aristocracy_vs_plutocracy"] == -30
    assert swe["capital"] == "stockholm"


def test_location_df_has_societal_columns():
    """location_df includes spiritualist_vs_humanist and aristocracy_vs_plutocracy."""
    config = load_config()
    path_resolver = PathResolver(config["game_path"], config["mod_path"])
    from core.data.location_data import LocationData

    ld = LocationData(path_resolver)
    ld.load_all()
    df = ld.get_merged_df()
    assert "spiritualist_vs_humanist" in df.columns
    assert "aristocracy_vs_plutocracy" in df.columns
    stockholm = df[df["location"] == "stockholm"].iloc[0]
    assert stockholm["spiritualist_vs_humanist"] == -50
    assert stockholm["aristocracy_vs_plutocracy"] == -30
