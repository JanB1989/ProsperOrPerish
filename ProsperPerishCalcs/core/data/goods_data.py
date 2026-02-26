import pandas as pd
import numpy as np
from .base_data import DataModule
from .goods_demand_data import GoodsDemandData

class GoodsData(DataModule):
    """Module for parsing and accessing game goods (vanilla and modded)."""

    def __init__(self, path_resolver):
        super().__init__(path_resolver)
        self.demand_module = GoodsDemandData(path_resolver)
        self.modded_df = pd.DataFrame()
        self.vanilla_df = pd.DataFrame()

    def load_all(self):
        """Loads all goods and demand data, applying Gospel logic."""
        # 1. Load vanilla gospel base from all relevant folders
        vanilla_goods_raw = self.load_vanilla_only("in_game/common/goods")
        vanilla_demand_raw = self.demand_module.load_vanilla_only("in_game/common/goods_demand")
        vanilla_category_raw = self.demand_module.load_vanilla_only("in_game/common/goods_demand_category")
        
        # 2. Resolve vanilla gospel state
        self.vanilla_df = self._resolve_state(vanilla_goods_raw, vanilla_demand_raw, vanilla_category_raw)
        
        # 3. Load modded adjustments from all relevant folders
        mod_goods_raw = self.load_mod_only("in_game/common/goods")
        mod_demand_raw = self.demand_module.load_mod_only("in_game/common/goods_demand")
        mod_category_raw = self.demand_module.load_mod_only("in_game/common/goods_demand_category")
        
        # 4. Merge modded data into vanilla gospel
        merged_goods_raw = self._merge_data(vanilla_goods_raw, mod_goods_raw)
        merged_demand_raw = self._merge_data(vanilla_demand_raw, mod_demand_raw)
        merged_category_raw = self._merge_data(vanilla_category_raw, mod_category_raw)
        
        # 5. Resolve final active state (replacement semantics)
        self.modded_df = self._resolve_state(merged_goods_raw, merged_demand_raw, merged_category_raw)

        # 6. Apply additive semantics for food: mod injections ADD to vanilla, not replace
        mod_food_delta = self._extract_injected_values(
            mod_demand_raw, mod_category_raw, self.vanilla_df.index.union(self.modded_df.index),
            goods_raw=mod_goods_raw
        )
        vanilla_food = self.vanilla_df['food'].reindex(self.modded_df.index, fill_value=0)
        delta = mod_food_delta.reindex(self.modded_df.index, fill_value=0)
        self.modded_df = self.modded_df.copy()
        self.modded_df['food'] = vanilla_food + delta

        return self.modded_df

    def _extract_injected_values(self, demand_raw, category_raw, good_names, goods_raw=None):
        """
        Extracts food (and transport_cost) values that mod files inject.
        Used for additive semantics: modded = vanilla + mod_injection.
        Returns a Series index by good name.
        """
        result = {}
        good_set = set(good_names)

        def collect_props(good_name, props):
            if good_name not in good_set or not isinstance(props, dict):
                return
            for attr in ['food', 'transport_cost']:
                if attr in props:
                    try:
                        result[good_name] = result.get(good_name, {})
                        result[good_name][attr] = float(props[attr])
                    except (ValueError, TypeError):
                        pass

        # First pass: extract from mod goods (keys may be prefixed: TRY_INJECT:rice, INJECT:wheat)
        if goods_raw:
            for key, props in goods_raw.items():
                if not isinstance(props, dict):
                    continue
                entity_name = key.split(":", 1)[-1] if ":" in key else key
                collect_props(entity_name, props)

        demand_containers = ['pop_demand', 'army_demand', 'navy_demand', 'special_demands']
        for container in demand_containers:
            if container in demand_raw and isinstance(demand_raw[container], dict):
                for good_name, props in demand_raw[container].items():
                    collect_props(good_name, props)

        if category_raw:
            for cat_name, props in category_raw.items():
                if not isinstance(props, dict):
                    continue
                if 'goods' in props and isinstance(props['goods'], list):
                    for good_name in props['goods']:
                        collect_props(good_name, props)
                collect_props(cat_name, props)

        if not result:
            return pd.Series(dtype=float)

        # Build series for 'food' (primary additive attribute)
        food_vals = {g: v.get('food', 0) for g, v in result.items() if 'food' in v}
        return pd.Series(food_vals)

    def _resolve_state(self, goods_raw, demand_raw, category_raw=None):
        """Resolves the state of goods by cross-referencing demand data."""
        # Convert goods to initial DataFrame
        df = self._to_df(goods_raw)
        
        if df.empty:
            return df

        # Cross-reference demand data from all possible containers in goods_demand
        demand_containers = ['pop_demand', 'army_demand', 'navy_demand', 'special_demands']
        
        # Helper to apply properties
        def apply_props(good_name, props):
            if not isinstance(props, dict):
                return
            for attr in ['food', 'transport_cost']:
                if attr in props:
                    try:
                        val = float(props[attr])
                        # Only update if current value is NaN (to preserve definition in common/goods)
                        if pd.isna(df.at[good_name, attr]):
                            df.at[good_name, attr] = val
                    except (ValueError, TypeError):
                        pass

        # First pass: Resolve from goods_demand
        for container in demand_containers:
            if container in demand_raw:
                container_data = demand_raw[container]
                if isinstance(container_data, dict):
                    for good_name, props in container_data.items():
                        if good_name in df.index:
                            apply_props(good_name, props)
        
        # Second pass: Resolve from goods_demand_category
        if category_raw:
            for cat_name, props in category_raw.items():
                if isinstance(props, dict):
                    # If the category has a 'goods' list, apply category props to those goods
                    if 'goods' in props and isinstance(props['goods'], list):
                        for good_name in props['goods']:
                            if good_name in df.index:
                                apply_props(good_name, props)
                    
                    # Also check if the category name itself is a good
                    if cat_name in df.index:
                        apply_props(cat_name, props)

        # Final pass: ensure engine defaults for anything still NaN
        df['transport_cost'] = df['transport_cost'].fillna(1.0)
        df['food'] = df['food'].fillna(0.0)
        
        return df

    def _to_df(self, raw_data):
        """Converts raw nested dict data to a flat DataFrame with normalized columns."""
        rows = []
        for name, props in raw_data.items():
            if isinstance(props, dict):
                row = {'name': name}
                for k, v in props.items():
                    if isinstance(v, dict):
                        # Flatten simple nested dicts like demand_add
                        for sub_k, sub_v in v.items():
                            if isinstance(sub_v, (int, float)):
                                row[f"{k}_{sub_k}"] = sub_v
                    else:
                        row[k] = v
                
                # Apply hardcoded engine defaults if missing (from readme.txt)
                if 'method' not in row:
                    row['method'] = 'farming'
                if 'default_market_price' not in row:
                    row['default_market_price'] = 1.0
                if 'transport_cost' not in row:
                    row['transport_cost'] = 1.0
                if 'food' not in row:
                    row['food'] = 0.0
                
                rows.append(row)
        
        if not rows:
            return pd.DataFrame()
            
        df = pd.DataFrame(rows).set_index('name')
        
        # Ensure common columns exist and are numeric for consistent analysis
        expected = ["method", "default_market_price", "transport_cost", "food"]
        for col in expected:
            if col not in df.columns:
                df[col] = np.nan
            elif col != "method":
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Final safety fill with engine defaults for any NaNs resulting from numeric conversion
        df['default_market_price'] = df['default_market_price'].fillna(1.0)
        df['transport_cost'] = df['transport_cost'].fillna(1.0)
        df['food'] = df['food'].fillna(0.0)
                
        return df

    def get_good(self, name):
        if name in self.modded_df.index:
            return self.modded_df.loc[name]
        return None

    def get_vanilla_good(self, name):
        if name in self.vanilla_df.index:
            return self.vanilla_df.loc[name]
        return None

    def get_food_good(self, is_modded=True):
        """Returns the good name for the canonical food good (food > 0, then max food value; tie: first by index)."""
        df = self.modded_df if is_modded else self.vanilla_df
        if df.empty or 'food' not in df.columns:
            return None
        food_positive = df[df['food'] > 0]
        if food_positive.empty:
            return None
        # Row with largest food value; sort by food descending then index for stable tie-break
        name = food_positive.sort_values('food', ascending=False).index[0]
        return name

    def get_food_good_price(self, is_modded=True):
        """Returns default_market_price of the food good from get_food_good, or None."""
        name = self.get_food_good(is_modded)
        if name is None:
            return None
        df = self.modded_df if is_modded else self.vanilla_df
        if name not in df.index:
            return None
        row = df.loc[name]
        price = row.get('default_market_price')
        if price is None or pd.isna(price):
            return None
        try:
            return float(price)
        except (TypeError, ValueError):
            return None
