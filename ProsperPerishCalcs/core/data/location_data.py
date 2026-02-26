import pandas as pd
import re
from .base_data import DataModule

# Keys that assign location ownership to a country at game start (wiki: Setup modding)
_OWNERSHIP_KEYS = frozenset({
    "own_control_core", "own_control_integrated", "own_control_conquered", "own_control_colony",
    "own_core", "own_conquered", "own_integrated", "own_colony",
    "control_core", "control",
})


class LocationData(DataModule):
    """Module for parsing and accessing location data (vanilla and modded)."""

    def __init__(self, path_resolver):
        super().__init__(path_resolver)
        self.locations_dict = {}
        self.pops_dict = {}
        self.dev_mods = {}
        self.hierarchy_list = []
        self.owner_dict = {}  # location -> country_tag at game start (None for unowned)
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

    def load_all(self):
        """Loads all location-related data from mirrored directories."""
        # 1. Load location templates
        # Path: in_game/map_data/location_templates.txt
        templates_data = self.load_directory("in_game/map_data")
        self.locations_dict = templates_data

        # 2. Load pops
        # Path: main_menu/setup/start/06_pops.txt (locations = { stockholm = { define_pop = {...} } })
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

        # 3. Load development modifiers
        # Path: main_menu/setup/start/14_development.txt (development = { base = -2, coastal = 5, ... })
        dev_data = self.load_directory("main_menu/setup/start")
        self.dev_mods = dev_data.get("development") or {}

        # 4. Load ownership (country tag per location at game start)
        self._load_ownership()

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
                    dev += float(self.dev_mods['coastal'])
                except (ValueError, TypeError):
                    pass
            return max(0.0, min(100.0, dev))

        merged['development'] = merged.apply(calculate_dev, axis=1)
        
        self.modded_df = merged # Store as instance variable
        return merged
