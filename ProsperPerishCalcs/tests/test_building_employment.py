import pytest

import pandas as pd

from core.parser.path_resolver import PathResolver
from core.data.building_data import BuildingData
from core.data.goods_data import GoodsData
from core.data.defines_data import DefinesData
from core.data.pop_data import PopData
from analysis.building_levels.building_analysis.utils import load_config

@pytest.fixture
def building_data():
    config = load_config()
    path_resolver = PathResolver(config['game_path'], config['mod_path'])
    data = BuildingData(path_resolver)
    data.load_all()
    return data

def test_building_employment_data_present(building_data):
    """Check if pop_type and employment_size_val are present for analyzed buildings."""
    
    # Specific buildings we are interested in
    target_buildings = [
        'farming_village', 'fishing_village', 'forest_village', 
        'sheep_farms', 'fruit_orchard', 'cookery'
    ]
    
    # Check vanilla_df
    v_df = building_data.vanilla_df
    for b in target_buildings:
        if b in v_df.index:
            assert not pd.isna(v_df.at[b, 'pop_type']), f"Missing pop_type for vanilla building {b}"
            assert v_df.at[b, 'employment_size_val'] > 0, f"Zero or missing employment_size_val for vanilla building {b}"
            
    # Check modded_df
    m_df = building_data.modded_df
    for b in target_buildings:
        if b in m_df.index:
            assert not pd.isna(m_df.at[b, 'pop_type']), f"Missing pop_type for modded building {b}"
            assert m_df.at[b, 'employment_size_val'] > 0, f"Zero or missing employment_size_val for modded building {b}"

def test_specific_employment_values(building_data):
    """Verify specific employment values for key buildings."""
    v_df = building_data.vanilla_df
    m_df = building_data.modded_df
    
    # farming_village in vanilla uses village_employment_size which is 1.0
    if 'farming_village' in v_df.index:
        assert v_df.at['farming_village', 'pop_type'] == 'peasants'
        assert v_df.at['farming_village', 'employment_size_val'] == 1.0
        
    # bailiff in vanilla uses bailiff_employment which is 0.2
    if 'bailiff' in v_df.index:
        assert v_df.at['bailiff', 'pop_type'] == 'soldiers'
        assert v_df.at['bailiff', 'employment_size_val'] == 0.2

    # tavern in modded should be present
    assert 'tavern' in m_df.index, "Tavern building missing from modded_df"
    assert m_df.at['tavern', 'pop_type'] == 'peasants'
    assert m_df.at['tavern', 'employment_size_val'] == 1.0


def test_tavern_modifier_food_valuation(building_data):
    """Modifier food (local_monthly_food) is valued at FOOD_PRICE from defines, not market price."""
    config = load_config()
    path_resolver = PathResolver(config['game_path'], config['mod_path'])
    goods_data = GoodsData(path_resolver)
    defines_data = DefinesData(path_resolver)
    pop_data = PopData(path_resolver)
    goods_data.load_all()
    defines_data.load_all()
    pop_data.load_all()

    comp = building_data.compare_production_methods(
        "tavern", goods_data=goods_data, defines_data=defines_data, pop_data=pop_data
    )
    modded_slots = comp["modded_slots"]
    assert len(modded_slots) >= 1, "Tavern should have at least one modded slot"

    # Tavern has local_monthly_food=120, one slot; output_value = 120 * FOOD_PRICE
    food_price = float(defines_data.get_define("NMarket", "FOOD_PRICE", 0.05))
    expected_output_value = 120.0 * food_price

    for slot in modded_slots:
        for pm_name, pm in slot.items():
            modifier_food = pm.get("modifier_food_output", 0)
            output_val = pm.get("output_value", 0)
            if modifier_food > 0:
                assert abs(output_val - expected_output_value) < 0.01, (
                    f"Modifier food output value should be {modifier_food} * FOOD_PRICE "
                    f"({expected_output_value}), got {output_val}"
                )
