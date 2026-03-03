import pytest

import pandas as pd

from core.parser.path_resolver import PathResolver
from core.data.location_ranks_data import LocationRanksData
from analysis.building_levels.building_analysis.utils import load_config


@pytest.fixture
def location_ranks_data():
    config = load_config()
    path_resolver = PathResolver(config["game_path"], config["mod_path"])
    data = LocationRanksData(path_resolver)
    data.load_all()
    return data


def test_desired_pop_df_columns(location_ranks_data):
    """desired_pop_df has columns for each location rank."""
    df = location_ranks_data.get_desired_pop_df()
    assert "rural_settlement" in df.columns
    assert "town" in df.columns
    assert "city" in df.columns


def test_desired_pop_df_rows(location_ranks_data):
    """desired_pop_df has rows for pop types including peasants."""
    df = location_ranks_data.get_desired_pop_df()
    assert "peasants" in df.index
    assert "burghers" in df.index
    assert "laborers" in df.index


def test_rural_settlement_all_peasants(location_ranks_data):
    """Rural settlements have 100% peasants (no desired_pop for other types in mod)."""
    df = location_ranks_data.get_desired_pop_df()
    assert df.loc["peasants", "rural_settlement"] == 1.0


def test_town_mod_values(location_ranks_data):
    """Town (mod) has expected desired_pop from pp_location_adjustments.
    Fixed values: raw from file (0.015 nobles = add 0.015 count), peasants = 1 - sum(others)."""
    df = location_ranks_data.get_desired_pop_df()
    # Mod: burghers 0.25, laborers 0.25, soldiers 0.10, nobles 0.015, clergy 0.04
    assert abs(df.loc["burghers", "town"] - 0.25) < 1e-6
    assert abs(df.loc["laborers", "town"] - 0.25) < 1e-6
    assert abs(df.loc["nobles", "town"] - 0.015) < 1e-6
    assert abs(df.loc["peasants", "town"] - 0.345) < 1e-6  # 1 - 0.25 - 0.25 - 0.10 - 0.015 - 0.04


def test_peasants_remainder(location_ranks_data):
    """Peasants equals 1 - sum(other pop types) per rank."""
    df = location_ranks_data.get_desired_pop_df()
    for col in df.columns:
        others = df.loc[df.index != "peasants", col].sum()
        expected_peasants = max(0.0, 1.0 - others)
        assert abs(df.loc["peasants", col] - expected_peasants) < 1e-6
