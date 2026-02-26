import pandas as pd
import numpy as np
from .base_data import DataModule

class GoodsDemandData(DataModule):
    """Module for parsing and accessing goods demand and demand categories."""

    def __init__(self, path_resolver):
        super().__init__(path_resolver)
        self.demands_df = pd.DataFrame()
        self.categories_df = pd.DataFrame()

    def load_all(self):
        """Loads all demand related data."""
        # Load demand categories first
        self.categories_raw = self.load_directory("in_game/common/goods_demand_category")
        self.categories_df = self._to_df(self.categories_raw)

        # Load demands
        self.demands_raw = self.load_directory("in_game/common/goods_demand")
        self.demands_df = self._to_df(self.demands_raw)
        
        return self.demands_df

    def _to_df(self, raw_data):
        """Converts raw nested dict data to a flat DataFrame."""
        rows = []
        for name, props in raw_data.items():
            if isinstance(props, dict):
                row = {'name': name}
                for k, v in props.items():
                    # We preserve nested dicts for complex demand logic
                    row[k] = v
                rows.append(row)
        
        if not rows:
            return pd.DataFrame()
            
        return pd.DataFrame(rows).set_index('name')
