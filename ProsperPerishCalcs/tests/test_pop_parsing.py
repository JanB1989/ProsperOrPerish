import pytest
import os
import sys
import pandas as pd

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.parser.path_resolver import PathResolver
from core.data.pop_data import PopData
from analysis.building_levels.building_analysis.utils import load_config

@pytest.fixture
def pop_data():
    config = load_config()
    path_resolver = PathResolver(config['game_path'], config['mod_path'])
    data = PopData(path_resolver)
    data.load_all()
    return data

def test_pop_types_coverage(pop_data):
    """Check if all 8 expected vanilla pop types are present in both dfs."""
    expected_pops = [
        'nobles', 'clergy', 'burghers', 'laborers', 
        'soldiers', 'peasants', 'tribesmen', 'slaves'
    ]
    
    # Check vanilla_df
    v_df = pop_data.vanilla_df
    assert len(v_df) == 8, f"Expected 8 vanilla pop types, found {len(v_df)}: {v_df.index.tolist()}"
    for p in expected_pops:
        assert p in v_df.index, f"Pop type '{p}' missing from vanilla_df"
        
    # Check modded_df
    m_df = pop_data.modded_df
    assert len(m_df) == 8, f"Expected 8 modded pop types, found {len(m_df)}: {m_df.index.tolist()}"
    for p in expected_pops:
        assert p in m_df.index, f"Pop type '{p}' missing from modded_df"

def test_pop_food_consumption_integrity(pop_data):
    """Check if pop_food_consumption is present and correctly resolved."""
    v_df = pop_data.vanilla_df
    m_df = pop_data.modded_df
    
    # Ensure no NaNs in food consumption
    assert v_df['pop_food_consumption'].isna().sum() == 0, "NaNs found in vanilla pop_food_consumption"
    assert m_df['pop_food_consumption'].isna().sum() == 0, "NaNs found in modded pop_food_consumption"
    
    # Verify specific modded change for peasants
    # Vanilla peasants: 1.0 (from 00_default.txt)
    # Modded peasants: 0.60 (from pp_pop_adjustments.txt)
    assert v_df.at['peasants', 'pop_food_consumption'] == 1.0
    assert m_df.at['peasants', 'pop_food_consumption'] == 0.60
    
    # Verify nobles (injected but value kept same in this case, or check if it merged)
    assert v_df.at['nobles', 'pop_food_consumption'] == 20.0
    assert m_df.at['nobles', 'pop_food_consumption'] == 20.0
