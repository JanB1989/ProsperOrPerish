import pytest
import os
import sys

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.parser.path_resolver import PathResolver
from core.data.defines_data import DefinesData
from analysis.building_levels.building_analysis.utils import load_config

@pytest.fixture
def defines_data():
    config = load_config()
    path_resolver = PathResolver(config['game_path'], config['mod_path'])
    data = DefinesData(path_resolver)
    data.load_all()
    return data

def test_food_price_resolution(defines_data):
    """Check if FOOD_PRICE is correctly resolved from vanilla and modded defines."""
    
    # Vanilla FOOD_PRICE should be 0.05 (based on grep)
    vanilla_food_price = defines_data.get_vanilla_define("NMarket", "FOOD_PRICE")
    assert vanilla_food_price == 0.05, f"Expected vanilla FOOD_PRICE 0.05, found {vanilla_food_price}"
    
    # Modded FOOD_PRICE should be 0.03 (based on pp_market_adjustments.txt)
    modded_food_price = defines_data.get_define("NMarket", "FOOD_PRICE")
    assert modded_food_price == 0.03, f"Expected modded FOOD_PRICE 0.03, found {modded_food_price}"

def test_defines_category_presence(defines_data):
    """Check if NMarket category is present in defines."""
    assert "NMarket" in defines_data.vanilla_defines
    assert "NMarket" in defines_data.modded_defines
