import os
import pandas as pd
import re
from .base_data import DataModule
from .building_data import BuildingData
from .country_setup_data import CountrySetupData
from .defines_data import DefinesData
from .location_ranks_data import LocationRanksData
from .pop_data import PopData
from .population_capacity_data import PopulationCapacityData, calculate_population_capacity
from .static_modifiers_data import StaticModifiersData
from .societal_values_data import SocietalValuesData

_POP_TYPES = ("burghers", "laborers", "soldiers", "nobles", "clergy")
_ALL_POP_TYPES = _POP_TYPES + ("peasants",)

# Keys that assign location ownership to a country at game start (wiki: Setup modding)
_OWNERSHIP_KEYS = frozenset({
    "own_control_core", "own_control_integrated", "own_control_conquered", "own_control_colony",
    "own_core", "own_conquered", "own_integrated", "own_colony",
    "control_core", "control",
})

# Topographies that are sea/lake (is_land=no). Per game localization: is_ownable=no means impassable, sea, or lake.
_TOPOGRAPHY_NON_OWNABLE = frozenset({
    "ocean", "deep_ocean", "coastal_ocean", "inland_sea", "narrows", "lakes", "high_lakes", "ocean_wasteland",
})


class LocationData(DataModule):
    """Module for parsing and accessing location data (vanilla and modded)."""

    def __init__(self, path_resolver):
        super().__init__(path_resolver)
        self.locations_dict = {}
        self.pops_dict = {}
        self.rank_dict = {}  # location_tag -> location_rank (town, city, rural_settlement)
        self.town_setup_dict = {}  # location_tag -> town_setup (from 07_cities_and_buildings)
        self.dev_mods = {}
        self.hierarchy_list = []
        self.owner_dict = {}  # location -> country_tag at game start (None for unowned)
        self.non_ownable_set = set()  # location IDs from default.map non_ownable block
        self.modded_df = pd.DataFrame()

    def _locations_from_value(self, val):
        """Extract location names from a parsed ownership value (list, dict keys, or single string)."""
        if val is None:
            return []
        if isinstance(val, list):
            return [str(v) for v in val if isinstance(v, str)]
        if isinstance(val, dict):
            return [str(k) for k in val.keys() if isinstance(k, str)]
        if isinstance(val, str):
            return [val]
        return []

    def _load_ownership(self):
        """Parse country setup to build location -> owner_tag mapping. Unowned locations are absent."""
        setup_data = self.load_directory("main_menu/setup/start")
        countries_block = setup_data.get("countries") or {}
        inner = countries_block.get("countries") if isinstance(countries_block, dict) else {}
        if not isinstance(inner, dict):
            return

        for tag, country_data in inner.items():
            if not isinstance(country_data, dict):
                continue
            for key in _OWNERSHIP_KEYS:
                val = country_data.get(key)
                for loc in self._locations_from_value(val):
                    self.owner_dict[loc] = tag

    def _load_non_ownable(self):
        """Load non_ownable location IDs from default.map. Mod overrides vanilla if present."""
        default_map_paths = self.path_resolver.resolve_path("in_game/map_data/default.map")
        for path in reversed(default_map_paths):  # mod last, so mod overrides vanilla
            if not os.path.exists(path):
                continue
            try:
                data = self.parser.parse(path)
                raw = data.get("non_ownable")
                if raw is None:
                    continue
                ids = []
                if isinstance(raw, list):
                    ids = [str(x) for x in raw if isinstance(x, str)]
                elif isinstance(raw, dict):
                    ids = list(raw.keys())
                self.non_ownable_set.update(ids)
                break  # use first (effective) file found
            except Exception:
                continue

    def load_all(self):
        """Loads all location-related data from mirrored directories."""
        # 1. Load location templates
        # Path: in_game/map_data/location_templates.txt
        templates_data = self.load_directory("in_game/map_data")
        self.locations_dict = templates_data

        # 2. Load pops (06_pops)
        pops_data = self.load_directory("main_menu/setup/start")
        locations_block = pops_data.get("locations") or {}
        if isinstance(locations_block, dict):
            for loc_name, loc_data in locations_block.items():
                if not isinstance(loc_data, dict):
                    continue
                total_pop = 0.0
                for key, val in loc_data.items():
                    if key.startswith("define_pop"):
                        for item in (val if isinstance(val, list) else [val]):
                            if isinstance(item, dict) and "size" in item:
                                total_pop += float(item["size"])
                self.pops_dict[loc_name] = total_pop

        # 2b. Parse location ranks and town_setup from 07_cities_and_buildings.txt (vanilla + mod)
        # Locations not listed = rural_settlement (valid locations = in hierarchy/templates)
        cities_paths = self.path_resolver.resolve_path("main_menu/setup/start/07_cities_and_buildings.txt")
        for path in cities_paths:
            if not os.path.exists(path):
                continue
            cities_data = self.parser.parse(path)
            cities_locations = cities_data.get("locations") or {}
            if isinstance(cities_locations, dict):
                for loc_name, loc_data in cities_locations.items():
                    if not isinstance(loc_data, dict):
                        continue
                    if "rank" in loc_data:
                        r = str(loc_data["rank"])
                        if ":" in r:
                            r = r.split(":")[-1]
                        self.rank_dict[loc_name] = r
                    if "town_setup" in loc_data:
                        self.town_setup_dict[loc_name] = str(loc_data["town_setup"])

        # 3. Load development modifiers
        # Path: main_menu/setup/start/14_development.txt
        dev_data = pops_data
        self.dev_mods = dev_data.get("development") or {}

        # 4. Load ownership (country tag per location at game start)
        self._load_ownership()

        # 4b. Load non_ownable from default.map (explicit list + topography handles sea/lake)
        self._load_non_ownable()

        # 5. Load hierarchy (definitions.txt)
        # This one is tricky because it's a deeply nested structure without many keys
        # For now, we'll use a simplified version of the old hierarchy parser
        # until the ParadoxParser is robust enough for this specific file.
        definitions_paths = self.path_resolver.resolve_path("in_game/map_data/definitions.txt")
        for path in definitions_paths:
            content = self.parser.read_file(path)
            content = self.parser.strip_comments(content)
            self.hierarchy_list.extend(self._parse_hierarchy_content(content))

        return self.locations_dict

    def _parse_hierarchy_content(self, content):
        """Internal helper to parse the definitions.txt hierarchy."""
        results = []
        
        def parse_block(text, parent_info):
            i = 0
            while i < len(text):
                match = re.search(r'(\w+)\s*=\s*\{', text[i:])
                if not match:
                    break
                
                name = match.group(1)
                start = i + match.end()
                
                depth = 1
                end = start
                while depth > 0 and end < len(text):
                    if text[end] == '{': depth += 1
                    elif text[end] == '}': depth -= 1
                    end += 1
                
                inner_content = text[start:end-1].strip()
                
                if '=' not in inner_content:
                    locs = inner_content.split()
                    for loc in locs:
                        entry = parent_info.copy()
                        entry["location"] = loc
                        entry["province"] = name
                        results.append(entry)
                else:
                    new_parent_info = parent_info.copy()
                    level_key = f"level_{len(parent_info)}"
                    new_parent_info[level_key] = name
                    parse_block(inner_content, new_parent_info)
                
                i = end
        
        parse_block(content, {})
        return results

    def get_merged_df(self):
        """Merges all loaded data into a single DataFrame."""
        if not self.hierarchy_list:
            return pd.DataFrame()

        df_hierarchy = pd.DataFrame(self.hierarchy_list)
        
        # Rename hierarchy columns
        rename_map = {
            "level_0": "super_region",
            "level_1": "macro_region",
            "level_2": "region",
            "level_3": "area"
        }
        df_hierarchy = df_hierarchy.rename(columns=rename_map)
        df_hierarchy = df_hierarchy.drop_duplicates(subset=['location'])

        # Prepare templates DataFrame
        loc_rows = []
        for loc_name, props in self.locations_dict.items():
            if isinstance(props, dict):
                row = props.copy()
                row['location'] = loc_name
                
                # Coastal detection
                is_coastal = False
                if 'harbor' in row and row['harbor'] == 'yes':
                    is_coastal = True
                elif 'natural_harbor_suitability' in row:
                    try:
                        if float(row['natural_harbor_suitability']) > 0:
                            is_coastal = True
                    except (ValueError, TypeError):
                        pass
                row['is_coastal'] = 'yes' if is_coastal else 'no'
                loc_rows.append(row)
        
        df_templates = pd.DataFrame(loc_rows)
        
        # Merge
        merged = pd.merge(df_hierarchy, df_templates, on="location", how="left")
        
        # Add population
        merged['population'] = merged['location'].map(self.pops_dict).fillna(0.0)

        # Add owner tag (country that owns the location at game start; pd.NA if unowned)
        merged['owner_tag'] = merged['location'].map(self.owner_dict)

        # Add location_rank and town_setup from 07_cities_and_buildings.
        # Locations not listed there are rural_settlement (valid locations = in hierarchy/templates).
        merged['location_rank'] = merged['location'].map(self.rank_dict).fillna("rural_settlement")
        merged['rank'] = merged['location_rank']  # Alias for capacity analyzer
        merged['town_setup'] = merged['location'].map(self.town_setup_dict)

        # raw_material from location templates (already in merged from df_templates)
        if 'raw_material' not in merged.columns:
            merged['raw_material'] = 'no_rgo'
        else:
            merged['raw_material'] = merged['raw_material'].fillna('no_rgo')

        # has_river, is_adjacent_to_lake: no static source in game files (runtime from map topology)
        if 'has_river' not in merged.columns:
            merged['has_river'] = 'no'
        else:
            merged['has_river'] = merged['has_river'].fillna('no')
        if 'is_adjacent_to_lake' not in merged.columns:
            merged['is_adjacent_to_lake'] = 'no'
        else:
            merged['is_adjacent_to_lake'] = merged['is_adjacent_to_lake'].fillna('no')

        # Add societal values from country setup (spiritualist_vs_humanist, aristocracy_vs_plutocracy)
        country_setup = CountrySetupData(self.path_resolver)
        country_setup.load_all()
        sv_df = country_setup.get_societal_values_df()
        merged = merged.merge(
            sv_df,
            left_on="owner_tag",
            right_on="owner_tag",
            how="left",
            suffixes=("", "_country"),
        )

        # Calculate development
        base_dev = float(self.dev_mods.get('base', 0))
        
        def calculate_dev(row):
            dev = base_dev
            for col in ['topography', 'vegetation', 'climate', 'region', 'area', 'province', 'location']:
                if col in row and row[col] in self.dev_mods:
                    try:
                        dev += float(self.dev_mods[row[col]])
                    except (ValueError, TypeError):
                        pass
            if row.get('is_coastal') == 'yes' and 'coastal' in self.dev_mods:
                try:
                    suitability = float(row.get('natural_harbor_suitability', 1.0))
                    dev += float(self.dev_mods['coastal']) * suitability
                except (ValueError, TypeError):
                    pass
            return max(0.0, min(100.0, dev))

        merged['development'] = merged.apply(calculate_dev, axis=1)

        # Population capacity from topography, vegetation, climate, river, development
        merged = self._add_population_capacity_column(merged)

        # is_ownable: from default.map non_ownable block + topography (sea/lake)
        merged["is_ownable"] = merged.apply(
            lambda row: (
                row["location"] not in self.non_ownable_set
                and (row.get("topography") or "") not in _TOPOGRAPHY_NON_OWNABLE
            ),
            axis=1,
        )
        # Wastelands (*_wasteland) are never ownable
        wasteland_mask = merged["topography"].fillna("").str.contains("_wasteland", regex=False)
        merged.loc[wasteland_mask, "is_ownable"] = False

        # Desired pop computation (location_rank + base_location + aristocracy/spiritualist)
        merged = self._add_desired_pop_columns(merged)
        merged = self._add_food_consumption_columns(merged)
        merged = self._add_victuals_market_columns(merged)

        self.modded_df = merged  # Store as instance variable
        return merged

    def _add_population_capacity_column(self, df):
        """Add population_capacity column from topography, vegetation, climate, river, development."""
        cap_data = PopulationCapacityData(self.path_resolver)
        cap_data.load_all()

        def calc_cap(row):
            topo = row.get("topography") or ""
            veg = row.get("vegetation") or ""
            clim = row.get("climate") or ""
            has_river = (row.get("has_river") or "").lower() in ("yes", "true", "1")
            dev = float(row.get("development", 0.0))
            return calculate_population_capacity(topo, veg, clim, has_river, dev, cap_data)

        df["population_capacity"] = df.apply(calc_cap, axis=1)
        return df

    def _add_desired_pop_columns(self, df):
        """Add per-source and total desired pop columns for each pop type."""
        ranks = LocationRanksData(self.path_resolver)
        ranks.load_all()
        desired_df = ranks.get_desired_pop_df()

        static_mod = StaticModifiersData(self.path_resolver)
        static_mod.load_all()

        societal = SocietalValuesData(self.path_resolver)

        _city_or_town = ("city", "town")

        for p in _POP_TYPES:
            def rank_val(rank, pop_type=p):
                if rank in desired_df.columns and pop_type in desired_df.index:
                    return desired_df.loc[pop_type, rank]
                return 0.0

            rank_raw = df["location_rank"].map(rank_val)
            if p == "clergy":
                base_raw = static_mod.get_base_scaled("clergy")
                aristo_raw = 0.0
                spirit_raw = df.apply(
                    lambda row: societal.get_effective_clergy_city_scaled(row.get("spiritualist_vs_humanist"))
                    if row.get("location_rank") in _city_or_town and pd.notna(row.get("owner_tag"))
                    else 0.0,
                    axis=1,
                )
            elif p == "nobles":
                base_raw = static_mod.get_base_scaled("nobles")
                spirit_raw = 0.0
                aristo_raw = df.apply(
                    lambda row: societal.get_effective_nobles_city_scaled(row.get("aristocracy_vs_plutocracy"))
                    if row.get("location_rank") in _city_or_town and pd.notna(row.get("owner_tag"))
                    else 0.0,
                    axis=1,
                )
            else:
                base_raw = 0.0
                aristo_raw = 0.0
                spirit_raw = 0.0

            # Scaled: base and aristocracy/spiritualist multiply by population
            # Fixed: location_rank adds raw count (no * pop)
            scaled_part = (base_raw + aristo_raw + spirit_raw) * df["population"]
            fixed_part = rank_raw
            df[f"{p}_desired_count"] = scaled_part + fixed_part
            df[f"{p}_desired_pct"] = (df[f"{p}_desired_count"] / df["population"].replace(0, pd.NA)).fillna(0.0)

            # Share columns: each source's contribution as fraction of total (0-1), sums to 1
            total = df[f"{p}_desired_count"]
            denom = total.replace(0, pd.NA)
            df[f"{p}_from_location_rank_share"] = (fixed_part / denom).fillna(0.0)
            df[f"{p}_from_base_location_share"] = (base_raw * df["population"] / denom).fillna(0.0)
            df[f"{p}_from_aristocracy_share"] = (aristo_raw * df["population"] / denom).fillna(0.0)
            df[f"{p}_from_spiritualist_share"] = (spirit_raw * df["population"] / denom).fillna(0.0)

        # Peasants: max(0, 1 - sum(other desired_pct))
        other_sum = sum(df[f"{p}_desired_pct"] for p in _POP_TYPES)
        df["peasants_desired_pct"] = (1.0 - other_sum).clip(lower=0.0)
        df["peasants_desired_count"] = df["population"] * df["peasants_desired_pct"]

        return df

    def _add_food_consumption_columns(self, df):
        """Add food_consumption_{pop_type}, total_food_consumption, and food_subsistence columns."""
        pop_data = PopData(self.path_resolver)
        pop_data.load_all()
        rates = pop_data.modded_df["pop_food_consumption"]

        total = pd.Series(0.0, index=df.index)
        for p in _ALL_POP_TYPES:
            rate = float(rates[p]) if p in rates.index else 0.0
            df[f"food_consumption_{p}"] = df[f"{p}_desired_count"] * rate
            total = total + df[f"food_consumption_{p}"]

        df["total_food_consumption"] = total

        # Subsistence agriculture: peasants * SUBSISTENCE_AGRICULTURE (assume all peasants unemployed)
        defines = DefinesData(self.path_resolver)
        defines.load_all()
        subsistence = float(defines.get_define("NLocation", "SUBSISTENCE_AGRICULTURE", 1.0))
        df["food_subsistence"] = df["peasants_desired_count"] * subsistence

        return df

    def _add_victuals_market_columns(self, df):
        """Add victuals_market_amount, food_victuals_market, and total_food_production columns.
        victuals_market_amount comes from pp_game_start conditions (capital + pop thresholds).
        food_victuals_market = amount * local_monthly_food from building modifier.
        total_food_production = food_subsistence + food_victuals_market.
        """
        building_data = BuildingData(self.path_resolver)
        building_data.load_all()
        victuals_building = building_data.get_building("victuals_market")
        food_per_level = 0.0
        if victuals_building and isinstance(victuals_building.get("modifier"), dict):
            try:
                food_per_level = float(victuals_building["modifier"].get("local_monthly_food", 0))
            except (TypeError, ValueError):
                pass

        # is_capital: location is capital of its owner (capital comes from country setup merge)
        is_capital = df["capital"].fillna("").astype(str) == df["location"].fillna("").astype(str)
        has_owner = df["owner_tag"].notna()

        # victuals_market_amount from pp_game_start:
        # - Capital with owner: +1
        # - Non-capital owned: (town and pop>20) or (city and pop>20) or (rural_settlement and pop>50)
        capital_gets_one = is_capital & has_owner
        rank_pop_ok = (
            ((df["location_rank"] == "town") & (df["population"] > 20))
            | ((df["location_rank"] == "city") & (df["population"] > 20))
            | ((df["location_rank"] == "rural_settlement") & (df["population"] > 50))
        )
        non_capital_gets_one = has_owner & ~is_capital & rank_pop_ok
        df["victuals_market_amount"] = (capital_gets_one | non_capital_gets_one).astype(int)

        df["food_victuals_market"] = df["victuals_market_amount"] * food_per_level
        df["total_food_production"] = df["food_subsistence"] + df["food_victuals_market"]

        return df

    def get_location_by_tag(self, location_tag: str):
        """Returns the location row for the given location tag (e.g. 'jiaxing', 'stockholm'), or None if not found."""
        df = self.modded_df if not self.modded_df.empty else self.get_merged_df()
        if df.empty:
            return None
        match = df[df['location'] == location_tag]
        if match.empty:
            return None
        return match.iloc[0]
