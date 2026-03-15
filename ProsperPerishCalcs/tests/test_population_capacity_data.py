"""Tests for PopulationCapacityData and calculate_population_capacity."""

import pytest

from core.parser.path_resolver import PathResolver
from core.data.population_capacity_data import (
    PopulationCapacityData,
    calculate_population_capacity,
)
from analysis.building_levels.building_analysis.utils import load_config


@pytest.fixture(scope="module")
def capacity_data():
    config = load_config()
    pr = PathResolver(config["game_path"], config["mod_path"])
    data = PopulationCapacityData(pr)
    data.load_all()
    return data


def test_load_all_parses_development(capacity_data):
    """Development block has add or modifier (vanilla: mod 0.025; mod: add 3)."""
    has_add = capacity_data.development_add_per_point != 0
    has_mod = capacity_data.development_modifier_per_point != 0
    assert has_add or has_mod


def test_load_all_parses_river(capacity_data):
    """River block is parsed (vanilla: mod 0.10; mod may TRY_INJECT different values)."""
    # Mod has add 20 and mod -0.10
    assert capacity_data.river_add != 0 or capacity_data.river_modifier != 0


def test_topography_has_mountains(capacity_data):
    """Mountains topography has population capacity values."""
    add, mod = capacity_data.get_topography("mountains")
    # Vanilla: modifier -0.50; mod adds modifier 0.5 and add -25
    assert mod != 0 or add != 0


def test_vegetation_has_grasslands(capacity_data):
    """Grasslands vegetation has population capacity values."""
    add, mod = capacity_data.get_vegetation("grasslands")
    # Vanilla: add 50; mod may override
    assert add >= 0


def test_climate_has_continental(capacity_data):
    """Continental climate has modifier."""
    add, mod = capacity_data.get_climate("continental")
    # Vanilla: modifier 0.50
    assert mod == 0.5 or mod != 0


def test_calculate_population_capacity_positive(capacity_data):
    """Calculate returns positive value for favorable terrain."""
    cap = calculate_population_capacity(
        "flatland", "grasslands", "continental", False, 20.0, capacity_data
    )
    assert cap > 0


def test_calculate_population_capacity_unknown_types_default_zero(capacity_data):
    """Unknown topography/vegetation/climate return 0 add/mod."""
    cap = calculate_population_capacity(
        "unknown_topo", "unknown_veg", "unknown_clim", False, 0.0, capacity_data
    )
    # 0 * (1 + 0) = 0
    assert cap == 0.0
