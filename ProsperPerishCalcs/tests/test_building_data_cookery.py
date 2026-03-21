"""Cookery PM maps derived from parsed building_types (mod + game)."""

import pytest

from core.parser.path_resolver import PathResolver
from core.data.building_data import (
    BuildingData,
    CookeryPmMaps,
    extract_unique_production_method_slots,
)
from analysis.building_levels.building_analysis.utils import load_config


@pytest.fixture
def building_data():
    config = load_config()
    path_resolver = PathResolver(config["game_path"], config["mod_path"])
    data = BuildingData(path_resolver)
    data.load_all()
    return data


def test_extract_unique_production_method_slots_cookery(building_data):
    b = building_data.get_building("cookery")
    assert b is not None
    slots = extract_unique_production_method_slots(b)
    assert len(slots) == 3
    assert "pp_cookery_khichdi" in slots[0]
    assert "pp_cookery_well_water" in slots[1]
    assert "pp_cookery_no_packaging" in slots[2]


def test_cookery_pm_maps(building_data):
    maps = building_data.cookery_pm_maps("cookery")
    assert isinstance(maps, CookeryPmMaps)
    assert maps.category("pp_cookery_khichdi") == "food"
    assert maps.category("pp_cookery_beer") == "drinks"
    assert maps.category("pp_cookery_tin_cans") == "packaging"
    assert maps.category("unknown_pm") == "other"
    # Parsed mod values (not stale notebook literals)
    assert maps.pm_good_inputs["pp_cookery_khichdi"]["saffron"] == pytest.approx(0.1)
    assert maps.pm_good_inputs["pp_cookery_khichdi"]["rice"] == pytest.approx(3.3)


def test_pm_trade_good_inputs_skips_meta(building_data):
    d = {
        "rice": 1.0,
        "produced": "victuals",
        "output": 1.65,
        "category": "building_maintenance",
    }
    assert building_data.pm_trade_good_inputs(d) == {"rice": 1.0}
