import pytest
import os
import sys
import pandas as pd

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.parser.path_resolver import PathResolver
from core.data.goods_data import GoodsData
from analysis.building_levels.building_analysis.utils import load_config

@pytest.fixture
def goods_data():
    config = load_config()
    path_resolver = PathResolver(config['game_path'], config['mod_path'])
    data = GoodsData(path_resolver)
    data.load_all()
    return data

def test_vanilla_goods_coverage(goods_data):
    """Check if all 74 expected vanilla goods are present in vanilla_df."""
    df = goods_data.vanilla_df
    assert not df.empty, "vanilla_df should not be empty"
    
    # Full list of 74 vanilla goods discovered from game files
    expected_goods = [
        'alum', 'amber', 'beer', 'beeswax', 'books', 'cannons', 'chili', 'clay', 
        'cloth', 'cloves', 'coal', 'cocoa', 'coffee', 'copper', 'cotton', 'dyes', 
        'elephants', 'fiber_crops', 'fine_cloth', 'firearms', 'fish', 'fruit', 
        'fur', 'furniture', 'gems', 'glass', 'goods_gold', 'horses', 'incense', 
        'iron', 'ivory', 'jewelry', 'lacquerware', 'lead', 'leather', 'legumes', 
        'liquor', 'livestock', 'lumber', 'maize', 'marble', 'masonry', 'medicaments', 
        'mercury', 'millet', 'naval_supplies', 'olives', 'paper', 'pearls', 'pepper', 
        'porcelain', 'potato', 'pottery', 'rice', 'saffron', 'salt', 'saltpeter', 
        'sand', 'silk', 'silver', 'slaves_goods', 'steel', 'stone', 'sugar', 'tar', 
        'tea', 'tin', 'tobacco', 'tools', 'weaponry', 'wheat', 'wild_game', 'wine', 'wool'
    ]
    
    assert len(df) == 74, f"Expected 74 vanilla goods, found {len(df)}: {df.index.tolist()}"
    
    missing = [g for g in expected_goods if g not in df.index]
    assert not missing, f"Missing vanilla goods: {missing}"

def test_vanilla_goods_fields_filled(goods_data):
    """Check if required economic fields are 100% present in vanilla_df."""
    df = goods_data.vanilla_df
    
    # method, default_market_price, transport_cost MUST ALWAYS be present
    
    # Check method
    method_nulls = df['method'].isna().sum()
    assert method_nulls == 0, f"Missing 'method' for {method_nulls} goods: {df[df['method'].isna()].index.tolist()}"
    
    # Check default_market_price
    price_nulls = df['default_market_price'].isna().sum()
    assert price_nulls == 0, f"Missing 'default_market_price' for {price_nulls} goods: {df[df['default_market_price'].isna()].index.tolist()}"
    
    # Check transport_cost
    transport_nulls = df['transport_cost'].isna().sum()
    assert transport_nulls == 0, f"Missing 'transport_cost' for {transport_nulls} goods: {df[df['transport_cost'].isna()].index.tolist()}"

def test_food_values_present(goods_data):
    """Check if food values are correctly resolved from demand scripts."""
    df = goods_data.vanilla_df
    
    # Some goods are known to have food values in vanilla (e.g., wheat, fish, livestock)
    food_goods = ['wheat', 'fish', 'livestock', 'maize', 'rice', 'millet', 'potato']
    
    for g in food_goods:
        if g in df.index:
            food_val = df.at[g, 'food']
            assert not pd.isna(food_val), f"Good '{g}' should have a resolved food value"
            assert food_val > 0, f"Good '{g}' should have a positive food value"

def test_modded_goods_coverage(goods_data):
    """Check if all 75 expected goods (74 vanilla + 1 modded) are present in the merged df."""
    df = goods_data.modded_df
    assert not df.empty, "merged df should not be empty"
    
    # Expected count: 74 vanilla + 'victuals'
    assert len(df) == 75, f"Expected 75 goods in merged df, found {len(df)}: {df.index.tolist()}"
    assert 'victuals' in df.index, "Modded good 'victuals' should be in the merged DataFrame"

def test_modded_goods_fields_filled(goods_data):
    """Check if required economic fields are 100% present in the merged df."""
    df = goods_data.modded_df
    
    # method, default_market_price, transport_cost MUST ALWAYS be present
    for col in ['method', 'default_market_price', 'transport_cost']:
        nulls = df[col].isna().sum()
        assert nulls == 0, f"Missing '{col}' for {nulls} goods in merged df: {df[df[col].isna()].index.tolist()}"

def test_modded_victuals_integration(goods_data):
    """Check if the modded 'victuals' good is correctly integrated in the merged df."""
    df = goods_data.modded_df
    assert 'victuals' in df.index, "Modded good 'victuals' should be in the merged DataFrame"
    
    # Victuals should have its price and other properties
    assert df.at['victuals', 'default_market_price'] == 3.0
    assert df.at['victuals', 'category'] == 'produced'


def test_vanilla_food_good_resolution(goods_data):
    """Vanilla get_food_good returns a good with food > 0."""
    name = goods_data.get_food_good(is_modded=False)
    assert name is not None, "Vanilla should have at least one good with food > 0"
    assert name in goods_data.vanilla_df.index, f"Food good '{name}' should be in vanilla_df"
    food_val = goods_data.vanilla_df.at[name, "food"]
    assert not pd.isna(food_val) and food_val > 0, f"Food good '{name}' should have food > 0"


def test_modded_food_good_resolution(goods_data):
    """Modded get_food_good returns a name; get_food_good_price returns a positive number."""
    name = goods_data.get_food_good(is_modded=True)
    assert name is not None, "Modded should have at least one good with food > 0"
    assert name in goods_data.modded_df.index, f"Food good '{name}' should be in modded_df"
    price = goods_data.get_food_good_price(is_modded=True)
    assert price is not None, "Modded food good should have a price"
    assert price > 0, f"Modded food good price should be positive, got {price}"
