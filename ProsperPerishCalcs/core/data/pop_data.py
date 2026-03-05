import pandas as pd
import numpy as np
from .base_data import DataModule

class PopData(DataModule):
    """Module for parsing and accessing pop types (vanilla and modded)."""

    def __init__(self, path_resolver):
        super().__init__(path_resolver)
        self.modded_df = pd.DataFrame()
        self.vanilla_df = pd.DataFrame()

    def load_all(self):
        """Loads all pop types and resolves vanilla and modded states."""
        relative_path = "in_game/common/pop_types"
        
        # 1. Load vanilla only
        vanilla_raw = self.load_vanilla_only(relative_path)
        self.vanilla_df = self._to_df(vanilla_raw)
        
        # 2. Load modded adjustments
        mod_raw = self.load_mod_only(relative_path)
        
        # 3. Merge modded into vanilla
        merged_raw = self._merge_data(vanilla_raw, mod_raw)
        self.modded_df = self._to_df(merged_raw)
        
        return self.modded_df

    def _to_df(self, raw_data):
        """Converts raw nested dict data to a flat DataFrame."""
        rows = []
        for name, props in raw_data.items():
            if isinstance(props, dict):
                row = {'name': name}
                for k, v in props.items():
                    if isinstance(v, dict):
                        # Flatten simple nested dicts if needed, but for pops we mainly care about top-level
                        row[k] = v
                    else:
                        row[k] = v
                rows.append(row)
        
        if not rows:
            return pd.DataFrame()
            
        df = pd.DataFrame(rows).set_index('name')
        
        # Ensure pop_food_consumption exists and is numeric
        if 'pop_food_consumption' not in df.columns:
            df['pop_food_consumption'] = 0.0
        else:
            df['pop_food_consumption'] = pd.to_numeric(df['pop_food_consumption'], errors='coerce').fillna(0.0)
            
        return df

    def get_pop_type(self, name):
        """Returns a modded pop type definition."""
        if name in self.modded_df.index:
            return self.modded_df.loc[name]
        return None

    def get_vanilla_pop_type(self, name):
        """Returns a vanilla pop type definition."""
        if name in self.vanilla_df.index:
            return self.vanilla_df.loc[name]
        return None
