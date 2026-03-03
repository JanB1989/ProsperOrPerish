import pytest

from core.parser.path_resolver import PathResolver
from core.data.static_modifiers_data import StaticModifiersData
from analysis.building_levels.building_analysis.utils import load_config


@pytest.fixture
def static_modifiers_data():
    config = load_config()
    path_resolver = PathResolver(config["game_path"], config["mod_path"])
    data = StaticModifiersData(path_resolver)
    data.load_all()
    return data


def test_location_base_values_clergy_nobles(static_modifiers_data):
    """Vanilla location_base_values from static_modifiers/location.txt:
    local_clergy_desired_pop_scaled = 0.005, local_nobles_desired_pop_scaled = 0.0025"""
    assert abs(static_modifiers_data.get_base_scaled("clergy") - 0.005) < 1e-9
    assert abs(static_modifiers_data.get_base_scaled("nobles") - 0.0025) < 1e-9
