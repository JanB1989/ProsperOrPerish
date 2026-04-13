from __future__ import annotations

from typing import NamedTuple

import pandas as pd
from .base_data import DataModule

# Keys on PM dicts returned by `compare_production_methods` (enrichment), not good inputs.
PM_COMPARE_META_KEYS = frozenset(
    {
        "produced",
        "output",
        "category",
        "worker_food_cost",
        "modifier_food_output",
        "output_price",
        "is_modifier_output",
        "input_cost",
        "output_value",
        "profit",
        "profit_margin",
        "epe",
    }
)

# Keys in building `unique_production_methods` PM blocks that are not trade-good inputs.
PM_SCRIPT_INPUT_SKIP_KEYS = frozenset({"produced", "output", "category"})


def extract_unique_production_method_slots(building_def: dict | None) -> list[dict[str, dict]]:
    """
    Return one dict per `unique_production_methods` slot: maps PM id -> PM body.

    Duplicate `unique_production_methods` blocks in a file are parsed as a list of
    per-slot dicts (see `DataModule._merge_unique_production_methods`).
    """
    if not building_def or "unique_production_methods" not in building_def:
        return []
    pm_data = building_def["unique_production_methods"]
    if isinstance(pm_data, list):
        return pm_data
    if isinstance(pm_data, dict):
        return [pm_data]
    return []


class CookeryPmMaps(NamedTuple):
    """Prosper-or-Perish-style cookery: three UPM slots (food / drinks / packaging)."""

    food: frozenset[str]
    drinks: frozenset[str]
    packaging: frozenset[str]
    pm_good_inputs: dict[str, dict[str, float]]

    def category(self, pm: str) -> str:
        if pm in self.food:
            return "food"
        if pm in self.drinks:
            return "drinks"
        if pm in self.packaging:
            return "packaging"
        return "other"


class BuildingData(DataModule):
    """Module for parsing and accessing building types (vanilla and modded)."""

    def __init__(self, path_resolver):
        super().__init__(path_resolver)
        self.modded_df = pd.DataFrame()
        self.vanilla_df = pd.DataFrame()
        self.production_methods_df = pd.DataFrame()
        self.vanilla_production_methods_df = pd.DataFrame()
        self.script_values = {}

    def load_all(self):
        """Loads all buildings and production methods into DataFrames."""
        # 0. Load script values for employment resolution
        self.script_values = self.load_vanilla_only("main_menu/common/script_values")
        # Also load in_game script values which might have overrides
        in_game_sv = self.load_vanilla_only("in_game/common/script_values")
        self.script_values.update(in_game_sv)
        # Load modded script values
        mod_sv = self.load_mod_only("in_game/common/script_values")
        self.script_values = self._merge_data(self.script_values, mod_sv)

        # 1. Buildings
        vanilla_buildings = self.load_vanilla_only("in_game/common/building_types")
        mod_buildings = self.load_mod_only("in_game/common/building_types")
        merged_buildings = self._merge_data(vanilla_buildings, mod_buildings)
        
        self.vanilla_df = self._to_df(vanilla_buildings)
        self.modded_df = self._to_df(merged_buildings)
        
        # 2. Production Methods
        vanilla_pms = self.load_vanilla_only("in_game/common/production_methods")
        mod_pms = self.load_mod_only("in_game/common/production_methods")
        merged_pms = self._merge_data(vanilla_pms, mod_pms)
        self.production_methods_df = self._to_df(merged_pms)
        self.vanilla_production_methods_df = self._to_df(vanilla_pms)

        return self.modded_df

    def _resolve_value(self, val):
        """Resolves a script value or literal to a float."""
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            try:
                return float(val)
            except (ValueError, TypeError):
                pass
            if val in self.script_values:
                sv = self.script_values[val]
                if isinstance(sv, dict) and 'value' in sv:
                    return self._resolve_value(sv['value'])
                return self._resolve_value(sv)
        return 0.0

    def _to_df(self, raw_data):
        """Converts raw nested dict data to a flat DataFrame."""
        rows = []
        for name, props in raw_data.items():
            if isinstance(props, dict):
                row = props.copy()
                row['name'] = name
                
                # Resolve employment
                if 'employment_size' in row:
                    row['employment_size_val'] = self._resolve_value(row['employment_size'])
                else:
                    row['employment_size_val'] = 0.0
                
                rows.append(row)
        
        df = pd.DataFrame(rows).set_index('name')
        
        # Ensure pop_type exists
        if 'pop_type' not in df.columns:
            df['pop_type'] = None
            
        return df

    def get_building(self, name):
        if name in self.modded_df.index:
            return self.modded_df.loc[name].to_dict()
        return None

    def get_vanilla_building(self, name):
        if name in self.vanilla_df.index:
            return self.vanilla_df.loc[name].to_dict()
        return None

    def get_production_method(self, name):
        if name in self.production_methods_df.index:
            return self.production_methods_df.loc[name].to_dict()
        return None

    def get_vanilla_production_method(self, name):
        if name in self.vanilla_production_methods_df.index:
            return self.vanilla_production_methods_df.loc[name].to_dict()
        return None

    def pm_trade_good_inputs(self, pm_def: dict) -> dict[str, float]:
        """
        Trade-good input amounts for one PM block (building `unique_production_methods` entry).

        Uses the same convention as `compare_production_methods` / `enrich_pm`: numeric inputs
        only, excluding `produced` / `output` / `category`. Script value references are resolved
        via `_resolve_value`.
        """
        if not isinstance(pm_def, dict):
            return {}
        out: dict[str, float] = {}
        for key, val in pm_def.items():
            if key in PM_SCRIPT_INPUT_SKIP_KEYS:
                continue
            amt = self._resolve_value(val)
            # Wide DataFrame rows from `get_production_method` include NaN for goods not in this PM.
            if pd.isna(amt) or amt == 0.0:
                continue
            out[key] = float(amt)
        return out

    def cookery_pm_maps(self, building_name: str = "cookery") -> CookeryPmMaps:
        """
        Slot membership (food / drinks / packaging) and per-PM good inputs for a cookery-style
        building with three `unique_production_methods` blocks.
        """
        b = self.get_building(building_name)
        if not b:
            raise ValueError(
                f"No modded building definition for {building_name!r}. "
                "Check mod `in_game/common/building_types` and config paths."
            )
        slots = extract_unique_production_method_slots(b)
        labels = ("food", "drinks", "packaging")
        slot_sets: list[frozenset[str]] = []
        for i, _label in enumerate(labels):
            if i < len(slots):
                slot_sets.append(frozenset(slots[i].keys()))
            else:
                slot_sets.append(frozenset())

        pm_good_inputs: dict[str, dict[str, float]] = {}
        for slot in slots:
            for pm_name, inner in slot.items():
                if isinstance(inner, dict):
                    pm_good_inputs[pm_name] = self.pm_trade_good_inputs(inner)

        return CookeryPmMaps(
            food=slot_sets[0],
            drinks=slot_sets[1],
            packaging=slot_sets[2],
            pm_good_inputs=pm_good_inputs,
        )

    def compare_production_methods(self, building_name, goods_data=None, defines_data=None, pop_data=None):
        """
        Returns a structured comparison of production methods for a building.
        Handles multiple slots (unique_production_methods blocks).
        """
        vanilla = self.get_vanilla_building(building_name) or {}
        modded = self.get_building(building_name) or {}
        
        comparison = {
            "building": building_name,
            "vanilla_slots": [],
            "modded_slots": []
        }
        
        def extract_slots(building_def):
            slots = list(extract_unique_production_method_slots(building_def))
            # Check possible_production_methods block (usually references to external PMs)
            if 'possible_production_methods' in building_def:
                ppm_data = building_def['possible_production_methods']
                if isinstance(ppm_data, list):
                    for pm_name in ppm_data:
                        if isinstance(pm_name, str):
                            pm_def = self.get_production_method(pm_name)
                            if pm_def:
                                slots.append({pm_name: pm_def})
                elif isinstance(ppm_data, str):
                    pm_def = self.get_production_method(ppm_data)
                    if pm_def:
                        slots.append({ppm_data: pm_def})
            return slots

        vanilla_slots = extract_slots(vanilla)
        modded_slots = extract_slots(modded)

        def enrich_pm(pm_def, num_slots, is_modded=True):
            if not isinstance(pm_def, dict): return pm_def
            
            enriched = pm_def.copy()
            building_def = modded if is_modded else vanilla
            
            if goods_data:
                input_cost = 0.0
                output_value = 0.0
                
                # 1. Direct Good Inputs
                for key, val in pm_def.items():
                    if key in ['produced', 'output', 'category']:
                        continue
                    
                    if isinstance(val, (int, float)) and not pd.isna(val):
                        good_info = goods_data.get_good(key) if is_modded else goods_data.get_vanilla_good(key)
                        if good_info is None:
                            good_info = goods_data.get_good(key)
                        
                        if good_info is not None:
                            price = good_info.get('default_market_price', 0.0)
                            input_cost += price * val
                
                # 2. Worker Food Consumption (Hidden Input Cost)
                # Use defines FOOD_PRICE (baseline wage food price), not food good market price.
                # Formula: employment * pop_food_consumption * FOOD_PRICE, spread over num_slots.
                worker_food_cost = 0.0
                if pop_data and num_slots > 0:
                    pop_type = building_def.get('pop_type')
                    employment = building_def.get('employment_size_val', 0.0)
                    if pop_type and employment > 0:
                        pop_info = pop_data.get_pop_type(pop_type) if is_modded else pop_data.get_vanilla_pop_type(pop_type)
                        food_cons = pop_info.get('pop_food_consumption', 0.0) if pop_info is not None else 0.0
                        food_price = defines_data.get_define("NMarket", "FOOD_PRICE", 0.0) if defines_data and is_modded else (defines_data.get_vanilla_define("NMarket", "FOOD_PRICE", 0.0) if defines_data else 0.0)
                        food_price = float(food_price) if food_price is not None else 0.0
                        total_building_food_cost = employment * food_cons * food_price
                        worker_food_cost = total_building_food_cost / num_slots
                        input_cost += worker_food_cost
                
                enriched['worker_food_cost'] = worker_food_cost
                
                # 3. Direct Good Output (PM produced/output)
                output_good = pm_def.get('produced')
                output_amount = pm_def.get('output', 0.0)
                
                # 4. Building Modifier Output (local_monthly_food)
                # Any building can have local_monthly_food in modifier; that is food produced.
                modifier_food_output = 0.0
                if isinstance(building_def, dict) and isinstance(building_def.get('modifier'), dict):
                    if 'local_monthly_food' in building_def['modifier']:
                        total_modifier_food = float(building_def['modifier']['local_monthly_food'])
                        modifier_food_output = total_modifier_food / num_slots if num_slots > 0 else 0.0
                enriched['modifier_food_output'] = modifier_food_output
                
                # Food price for valuing modifier output (abstract food)
                # Use FOOD_PRICE from defines only - same as worker cost, not market price.
                food_price_for_modifier = 0.0
                if defines_data:
                    fp = defines_data.get_define("NMarket", "FOOD_PRICE", 0.0) if is_modded else defines_data.get_vanilla_define("NMarket", "FOOD_PRICE", 0.0)
                    food_price_for_modifier = float(fp) if fp is not None else 0.0
                
                # PM output value
                if output_good and not pd.isna(output_good):
                    good_info = goods_data.get_good(output_good) if is_modded else goods_data.get_vanilla_good(output_good)
                    if good_info is None:
                        good_info = goods_data.get_good(output_good)
                    price = 0.0
                    if good_info is not None:
                        p = good_info.get('default_market_price', 0.0)
                        price = float(p) if p is not None and not pd.isna(p) else 0.0
                    if price == 0 and goods_data:
                        fallback = goods_data.get_food_good_price(is_modded)
                        if fallback is not None:
                            price = fallback
                    if price == 0 and defines_data:
                        price = float(defines_data.get_define("NMarket", "FOOD_PRICE", 0.0) if is_modded else defines_data.get_vanilla_define("NMarket", "FOOD_PRICE", 0.0))
                    output_value += price * output_amount
                    enriched['output_price'] = price
                    enriched['produced'] = output_good
                    enriched['output'] = output_amount
                elif modifier_food_output > 0:
                    # Only modifier food (no PM output): set produced='food' for backward compatibility
                    enriched['is_modifier_output'] = True
                    enriched['produced'] = 'food'
                    enriched['output'] = modifier_food_output
                    enriched['output_price'] = food_price_for_modifier
                
                # Add modifier food value to output_value
                output_value += modifier_food_output * food_price_for_modifier
                
                enriched['input_cost'] = input_cost
                enriched['output_value'] = output_value
                enriched['profit'] = output_value - input_cost
                if input_cost > 0:
                    enriched['profit_margin'] = (output_value / input_cost) - 1
                
                # Calculate Equilibrium Production Efficiency (EPE)
                # Profit = (Output_Value * (1 + EPE)) - Input_Cost
                # For Profit = 0: (Output_Value * (1 + EPE)) = Input_Cost
                # 1 + EPE = Input_Cost / Output_Value
                # EPE = (Input_Cost / Output_Value) - 1
                if output_value > 0:
                    enriched['epe'] = (input_cost / output_value) - 1
                else:
                    enriched['epe'] = 0.0
            
            return enriched

        comparison["vanilla_slots"] = [
            {name: enrich_pm(def_, len(vanilla_slots), False) for name, def_ in slot.items()} 
            for slot in vanilla_slots
        ]
        comparison["modded_slots"] = [
            {name: enrich_pm(def_, len(modded_slots), True) for name, def_ in slot.items()} 
            for slot in modded_slots
        ]
        
        return comparison
