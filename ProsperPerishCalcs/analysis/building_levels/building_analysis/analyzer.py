import itertools
import os

import pandas as pd

from core.parser.path_resolver import PathResolver
from core.data.location_data import LocationData
from core.data.building_data import BuildingData

from .parser import ParadoxParser
from .utils import get_path


class CapacityAnalyzer:
    def __init__(self, game_path=None, mod_path=None):
        self.game_path = game_path or get_path("game_path")
        self.mod_path = mod_path or get_path("mod_path")
        self.parser = ParadoxParser()

        # Initialize new live data architecture
        self.path_resolver = PathResolver(self.game_path, self.mod_path)
        self.location_data = LocationData(self.path_resolver)
        self.building_data = BuildingData(self.path_resolver)
        
        # Load data live
        print("Loading live game data...")
        self.location_data.load_all()
        self.building_data.load_all()
        
        self.building_map = {
            "Fruit Orchard": "fruit_orchard_max_level_modifier",
            "Sheep Farm": "sheep_farms_max_level_modifier",
            "Farming Village": "farming_village_max_level_modifier",
            "Fishing Village": "fishing_village_max_level_modifier",
            "Forest Village": "forest_village_max_level_modifier"
        }
        # Scaling factors from pp_building_caps.txt
        self.scaling = {
            "Fruit Orchard": {"dev": 0.35, "pop": 0.025},
            "Sheep Farm": {"dev": 0.2, "pop": 0.015},
            "Farming Village": {"dev": 0.35, "pop": 0.025},
            "Fishing Village": {"dev": 0.35, "pop": 0.025},
            "Forest Village": {"dev": 0.35, "pop": 0.025}
        }
        self.base_levels = 2.0

    def get_full_analysis_df(self, include_rank=True, include_rgo=True):
        data = self.parser.get_all_data(self.mod_path)
        climates = data["climate"]
        topographies = data["topography"]
        vegetations = data["vegetation"]
        ranks = data["rank"]
        statics = data["static"]
        rgos = data["rgo"]

        # Combinations of factors
        combinations = list(itertools.product(
            climates.keys(),
            topographies.keys(),
            vegetations.keys(),
            ranks.keys(),
            ['coastal', 'non_coastal'],
            ['river', 'non_river'],
            ['lake', 'non_lake'],
            (['no_rgo'] + list(rgos.keys())) if include_rgo else ['no_rgo']
        ))
        
        rows = []
        for climate, topo, veg, rank, coastal_status, river_status, lake_status, rgo_status in combinations:
            for building_name, modifier_key in self.building_map.items():
                c_val = climates.get(climate, {}).get(modifier_key, 0.0)
                t_val = topographies.get(topo, {}).get(modifier_key, 0.0)
                v_val = vegetations.get(veg, {}).get(modifier_key, 0.0)
                
                r_val = 0.0
                if include_rank and rank != 'none':
                    r_val = ranks.get(rank, {}).get(modifier_key, 0.0)
                
                # Water bonuses from static modifiers
                s_val = 0.0
                if coastal_status == 'coastal':
                    s_val += statics.get('coastal', {}).get(modifier_key, 0.0)
                if river_status == 'river':
                    s_val += statics.get('river', {}).get(modifier_key, 0.0)
                if lake_status == 'lake':
                    s_val += statics.get('lake', {}).get(modifier_key, 0.0)
                
                # RGO bonus
                rgo_val = 0.0
                if include_rgo and rgo_status != 'no_rgo':
                    rgo_val = rgos.get(rgo_status, {}).get(modifier_key, 0.0)
                
                total = c_val + t_val + v_val + r_val + s_val + rgo_val
                
                res_row = {
                    "Building": building_name,
                    "Climate": climate,
                    "Topography": topo,
                    "Vegetation": veg,
                    "Coastal": coastal_status,
                    "River": river_status,
                    "Lake": lake_status,
                    "Climate Bonus": c_val,
                    "Topography Bonus": t_val,
                    "Vegetation Bonus": v_val,
                    "Water Bonus": s_val,
                    "Total Bonus": total
                }
                
                if include_rank:
                    res_row["Rank"] = rank
                    res_row["Rank Bonus"] = r_val
                if include_rgo:
                    res_row["RGO"] = rgo_status
                    res_row["RGO Bonus"] = rgo_val
                    
                rows.append(res_row)
        
        df = pd.DataFrame(rows)
        return df.round(2)

    def get_summary_table(self):
        df = self.get_full_analysis_df()
        summary = df[["Building", "Vegetation", "Topography", "Climate", "Rank", "Coastal", "Total Bonus"]]
        return summary

    def get_modifier_sources_df(self, building_name=None):
        data = self.parser.get_all_data(self.mod_path)
        
        buildings_to_show = [building_name] if building_name else list(self.building_map.keys())
        
        source_data = []
        
        def process_category(cat_name, cat_dict):
            cat_rows = []
            for key, mods in cat_dict.items():
                row = {"Category": cat_name, "Source": key}
                row_sum = 0.0
                has_any_bonus = False
                for b_name in buildings_to_show:
                    mod_key = self.building_map[b_name]
                    val = mods.get(mod_key, 0.0)
                    row[b_name] = val
                    row_sum += val
                    if val != 0:
                        has_any_bonus = True
                
                if has_any_bonus:
                    row["Row Sum"] = row_sum
                    cat_rows.append(row)
            
            if cat_rows:
                total_row = {"Category": cat_name, "Source": f"TOTAL {cat_name.upper()}"}
                for b_name in buildings_to_show:
                    total_row[b_name] = sum(r[b_name] for r in cat_rows)
                total_row["Row Sum"] = sum(r["Row Sum"] for r in cat_rows)
                cat_rows.append(total_row)
                source_data.extend(cat_rows)
                source_data.append({"Category": "", "Source": ""})
        
        process_category("Climate", data["climate"])
        process_category("Topography", data["topography"])
        process_category("Vegetation", data["vegetation"])
        process_category("Rank", data["rank"])
        process_category("Static", data["static"])
        process_category("RGO", data["rgo"])
        
        if source_data and source_data[-1]["Source"] == "":
            source_data.pop()

        if source_data:
            grand_total = {"Category": "GRAND TOTAL", "Source": "ALL SOURCES"}
            for b_name in buildings_to_show:
                grand_total[b_name] = sum(r[b_name] for r in source_data if "TOTAL" in r["Source"])
            grand_total["Row Sum"] = sum(r["Row Sum"] for r in source_data if "TOTAL" in r["Source"])
            source_data.append(grand_total)

        df = pd.DataFrame(source_data)
        return df.round(2)

    def calculate_capacities_for_locations(self, locations_df, building_name=None, default_rank='rural_settlement'):
        data = self.parser.get_all_data(self.mod_path)
        climates = data["climate"]
        topographies = data["topography"]
        vegetations = data["vegetation"]
        ranks = data["rank"]
        statics = data["static"]
        rgos = data["rgo"]
        
        buildings_to_process = [building_name] if building_name else list(self.building_map.keys())
        
        required_cols = ['location', 'climate', 'topography', 'vegetation']
        missing_cols = [col for col in required_cols if col not in locations_df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns in locations_df: {missing_cols}")
        
        if 'rank' not in locations_df.columns:
            locations_df = locations_df.copy()
            locations_df['rank'] = default_rank
        
        if 'is_coastal' not in locations_df.columns:
            locations_df = locations_df.copy()
            locations_df['is_coastal'] = 'no'
        if 'has_river' not in locations_df.columns:
            locations_df = locations_df.copy()
            locations_df['has_river'] = 'no'
        if 'is_adjacent_to_lake' not in locations_df.columns:
            locations_df = locations_df.copy()
            locations_df['is_adjacent_to_lake'] = 'no'
        
        locations_df = locations_df.copy()
        locations_df['coastal_status'] = locations_df['is_coastal'].map({'yes': 'coastal', 'no': 'non_coastal'}).fillna('non_coastal')
        locations_df['river_status'] = locations_df['has_river'].map({'yes': 'river', 'no': 'non_river'}).fillna('non_river')
        locations_df['lake_status'] = locations_df['is_adjacent_to_lake'].map({'yes': 'lake', 'no': 'non_lake'}).fillna('non_lake')
        
        rows = []
        for idx, row in locations_df.iterrows():
            climate = row['climate']
            topo = row['topography']
            veg = row['vegetation']
            rank = row['rank']
            coastal_status = row['coastal_status']
            river_status = row['river_status']
            lake_status = row['lake_status']
            rgo_good = row.get('raw_material', 'no_rgo')
            if pd.isna(rgo_good): rgo_good = 'no_rgo'
            
            for b_name in buildings_to_process:
                modifier_key = self.building_map[b_name]
                
                c_val = climates.get(climate, {}).get(modifier_key, 0.0)
                t_val = topographies.get(topo, {}).get(modifier_key, 0.0)
                v_val = vegetations.get(veg, {}).get(modifier_key, 0.0)
                r_val = ranks.get(rank, {}).get(modifier_key, 0.0)
                
                s_val = 0.0
                if coastal_status == 'coastal':
                    s_val += statics.get('coastal', {}).get(modifier_key, 0.0)
                if river_status == 'river':
                    s_val += statics.get('river', {}).get(modifier_key, 0.0)
                if lake_status == 'lake':
                    s_val += statics.get('lake', {}).get(modifier_key, 0.0)
                
                rgo_val = rgos.get(rgo_good, {}).get(modifier_key, 0.0)
                
                pop_val = row.get('population', 0.0)
                dev_val = row.get('development', 0.0)
                
                pop_bonus = pop_val * self.scaling[b_name]['pop']
                dev_bonus = dev_val * self.scaling[b_name]['dev']
                
                total = self.base_levels + c_val + t_val + v_val + r_val + s_val + rgo_val + pop_bonus + dev_bonus
                
                result_row = {
                    "Building": b_name,
                    "Location": row['location'],
                    "Climate": climate,
                    "Topography": topo,
                    "Vegetation": veg,
                    "Rank": rank,
                    "Coastal": coastal_status,
                    "River": river_status,
                    "Lake": lake_status,
                    "RGO": rgo_good,
                    "Population": pop_val,
                    "Development": dev_val,
                    "Base": self.base_levels,
                    "Climate Bonus": c_val,
                    "Topography Bonus": t_val,
                    "Vegetation Bonus": v_val,
                    "Rank Bonus": r_val,
                    "Water Bonus": s_val,
                    "RGO Bonus": rgo_val,
                    "Pop Bonus": pop_bonus,
                    "Dev Bonus": dev_bonus,
                    "Total Bonus": total
                }
                
                for col in ['province', 'area', 'region', 'macro_region', 'super_region']:
                    if col in row:
                        result_row[col.capitalize()] = row[col]
                
                rows.append(result_row)
        
        return pd.DataFrame(rows).round(2)

    def get_grouped_capacity_analysis(self, locations_df, group_by='region', building_name=None):
        df_full = self.calculate_capacities_for_locations(locations_df, building_name=building_name)
        
        group_col = group_by.capitalize()
        if group_col not in df_full.columns:
            group_col = group_by
            
        if group_col not in df_full.columns:
            raise ValueError(f"Column '{group_by}' not found in hierarchy data.")

        grouped = df_full.groupby([group_col, 'Building']).agg({
            'Total Bonus': ['mean', 'sum', 'max', 'min'],
            'Population': 'sum',
            'Development': 'sum',
            'Location': 'count'
        })
        
        grouped.columns = [f"{col}_{stat}" if stat else col for col, stat in grouped.columns]
        grouped = grouped.rename(columns={'Location_count': 'Location Count'})
        
        return grouped.round(2)

    def get_comprehensive_location_df(self, locations_df):
        print("Calculating capacities for all buildings...")
        df_full = self.calculate_capacities_for_locations(locations_df)
        
        df_pivoted = df_full.pivot_table(index='Location', columns='Building', values='Total Bonus', aggfunc='first')
        df_pivoted.columns = [f"{col} Capacity" for col in df_pivoted.columns]
        
        loc_info_cols = [
            'Location', 'Climate', 'Topography', 'Vegetation', 'Rank', 'Coastal', 'RGO',
            'Population', 'Development', 'Province', 'Area', 'Region', 'Macro_region', 'Super_region'
        ]
        loc_info_cols = [col for col in loc_info_cols if col in df_full.columns]
        df_loc_info = df_full[loc_info_cols].drop_duplicates(subset=['Location']).set_index('Location')
        
        comprehensive_df = df_loc_info.join(df_pivoted)
        
        building_cols = [f"{col} Capacity" for col in self.building_map.keys()]
        
        print("Calculating extensive geographical statistics...")
        geo_levels = ['Province', 'Area', 'Region', 'Macro_region', 'Super_region']
        
        for level in geo_levels:
            if level in comprehensive_df.columns:
                print(f"  Processing {level} level...")
                comprehensive_df[f'{level} Location Count'] = comprehensive_df.groupby(level)['Population'].transform('count')
                comprehensive_df[f'{level} Total Population'] = comprehensive_df.groupby(level)['Population'].transform('sum')
                comprehensive_df[f'{level} Total Development'] = comprehensive_df.groupby(level)['Development'].transform('sum')
                
                for b_col in building_cols:
                    comprehensive_df[f"{b_col} ({level} Avg)"] = comprehensive_df.groupby(level)[b_col].transform('mean')
                    comprehensive_df[f"{b_col} ({level} Total)"] = comprehensive_df.groupby(level)[b_col].transform('sum')
        
        return comprehensive_df.reset_index().round(2)

    def filter_locations(self, df, filters=None):
        """
        Applies arbitrary filters to a DataFrame.
        filters: dict of {column: value} or {column: [values]}
        """
        if not filters:
            return df
        
        filtered_df = df.copy()
        for col, val in filters.items():
            if col not in filtered_df.columns:
                print(f"Warning: Column '{col}' not found for filtering.")
                continue
            
            if isinstance(val, list):
                filtered_df = filtered_df[filtered_df[col].isin(val)]
            else:
                filtered_df = filtered_df[filtered_df[col] == val]
        
        return filtered_df

    def run_standard_analysis(self, locations_df, group_by='region', filters=None, top_n=15):
        """
        High-level method to filter, calculate capacities, and group results.
        """
        # Apply filters first
        df_filtered = self.filter_locations(locations_df, filters)
        
        if df_filtered.empty:
            print("Warning: Filtered DataFrame is empty.")
            return pd.DataFrame()

        # Run grouped analysis
        df_grouped = self.get_grouped_capacity_analysis(df_filtered, group_by=group_by)
        
        # Format results for display
        results = {}
        for building in self.building_map.keys():
            try:
                building_data = df_grouped.xs(building, level='Building')
                top_data = building_data.sort_values('Total Bonus_mean', ascending=False).head(top_n)
                results[building] = top_data
            except Exception as e:
                print(f"Error processing {building} in standard analysis: {e}")
        
        return results

    def get_outlier_analysis(self, locations_df, building_name, filters=None, top_n=40):
        """
        Replicates the outlier analysis logic.
        """
        df_filtered = self.filter_locations(locations_df, filters)
        
        if df_filtered.empty:
            return pd.DataFrame(), pd.DataFrame()

        df_capacities = self.calculate_capacities_for_locations(df_filtered, building_name=building_name)
        df_sorted = df_capacities.sort_values('Total Bonus', ascending=False)
        
        top_outliers = df_sorted.head(top_n)
        bottom_outliers = df_sorted[df_sorted['Total Bonus'] > 0].tail(top_n)
        
        return top_outliers, bottom_outliers
