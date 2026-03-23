import re
import os

class ParadoxParser:
    def __init__(self):
        self.modifiers = [
            "fruit_orchard_max_level_modifier",
            "sheep_farms_max_level_modifier",
            "farming_village_max_level_modifier",
            "fishing_village_max_level_modifier",
            "forest_village_max_level_modifier"
        ]
        self.var_map = {
            "fruit_orchard_max_level_modifier": "pp_fruit_orchard_fixed_env_bonus",
            "sheep_farms_max_level_modifier": "pp_sheep_farms_fixed_env_bonus",
            "farming_village_max_level_modifier": "pp_farming_village_fixed_env_bonus",
            "fishing_village_max_level_modifier": "pp_fishing_village_fixed_env_bonus",
            "forest_village_max_level_modifier": "pp_forest_village_fixed_env_bonus"
        }

    def parse_file(self, file_path, block_keyword):
        """
        Parses a Paradox mod file and extracts modifiers within specific blocks.
        block_keyword: 'location_modifier' or 'rank_modifier'
        """
        if not os.path.exists(file_path):
            print(f"Warning: File not found: {file_path}")
            return {}

        with open(file_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()

        results = {}
        
        # Find TRY_INJECT or TRY_REPLACE blocks
        block_pattern = re.compile(r'(?:TRY_INJECT|TRY_REPLACE):(\w+)\s*=\s*\{', re.IGNORECASE)
        
        pos = 0
        while True:
            match = block_pattern.search(content, pos)
            if not match:
                break
            
            entity_name = match.group(1)
            start_idx = match.end()
            
            # Find the matching closing brace for this TRY block
            depth = 1
            end_idx = start_idx
            while depth > 0 and end_idx < len(content):
                if content[end_idx] == '{':
                    depth += 1
                elif content[end_idx] == '}':
                    depth -= 1
                end_idx += 1
            
            block_content = content[start_idx:end_idx-1]
            pos = end_idx
            
            # Now find the modifier sub-block (location_modifier or rank_modifier)
            mod_subblock_pattern = re.compile(rf'{block_keyword}\s*=\s*\{{', re.IGNORECASE)
            sub_match = mod_subblock_pattern.search(block_content)
            
            if sub_match:
                sub_start = sub_match.end()
                sub_depth = 1
                sub_end = sub_start
                while sub_depth > 0 and sub_end < len(block_content):
                    if block_content[sub_end] == '{':
                        sub_depth += 1
                    elif block_content[sub_end] == '}':
                        sub_depth -= 1
                    sub_end += 1
                
                mod_content = block_content[sub_start:sub_end-1]
                
                # Extract our target modifiers
                entity_modifiers = {}
                for mod in self.modifiers:
                    # Match mod = value (handles comments)
                    val_match = re.search(rf'{mod}\s*=\s*(-?\d+\.?\d*)', mod_content)
                    if val_match:
                        entity_modifiers[mod] = float(val_match.group(1))
                    else:
                        entity_modifiers[mod] = 0.0
                
                results[entity_name] = entity_modifiers
            else:
                # If no modifier block found, initialize with zeros
                results[entity_name] = {mod: 0.0 for mod in self.modifiers}
                
        return results

    def parse_precalc_file(self, file_path):
        """
        Parses the pp_building_capacity_values.txt file to extract fixed bonuses.
        """
        if not os.path.exists(file_path):
            print(f"Warning: Precalc file not found: {file_path}")
            return {"climate": {}, "topography": {}, "vegetation": {}, "static": {"coastal": {}, "river": {}, "lake": {}}, "rgo": {}}

        with open(file_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()

        data = {"climate": {}, "topography": {}, "vegetation": {}, "static": {"coastal": {}, "river": {}, "lake": {}}, "rgo": {}}
        
        # Mapping building script values to our internal modifier keys
        building_script_map = {
            "pp_fruit_orchard_capacity_value": "fruit_orchard_max_level_modifier",
            "pp_fishing_village_capacity_value": "fishing_village_max_level_modifier",
            "pp_sheep_farms_capacity_value": "sheep_farms_max_level_modifier",
            "pp_farming_village_capacity_value": "farming_village_max_level_modifier",
            "pp_forest_village_capacity_value": "forest_village_max_level_modifier"
        }

        for script_name, mod_key in building_script_map.items():
            # Find the block for this building
            block_pattern = re.compile(rf'{script_name}\s*=\s*\{{', re.IGNORECASE)
            match = block_pattern.search(content)
            if not match:
                continue
            
            start_idx = match.end()
            depth = 1
            end_idx = start_idx
            while depth > 0 and end_idx < len(content):
                if content[end_idx] == '{':
                    depth += 1
                elif content[end_idx] == '}':
                    depth -= 1
                end_idx += 1
            
            block_content = content[start_idx:end_idx-1]

            # Parse Climate in this block
            climate_matches = re.finditer(r'limit\s*=\s*\{\s*climate\s*=\s*(\w+)\s*\}\s*add\s*=\s*(-?\d+\.?\d*)', block_content, re.DOTALL)
            for m in climate_matches:
                name = m.group(1)
                val = float(m.group(2))
                if name not in data["climate"]: data["climate"][name] = {}
                data["climate"][name][mod_key] = val

            # Parse Topography in this block
            topo_matches = re.finditer(r'limit\s*=\s*\{\s*topography\s*=\s*(\w+)\s*\}\s*add\s*=\s*(-?\d+\.?\d*)', block_content, re.DOTALL)
            for m in topo_matches:
                name = m.group(1)
                val = float(m.group(2))
                if name not in data["topography"]: data["topography"][name] = {}
                data["topography"][name][mod_key] = val

            # Parse Vegetation in this block
            veg_matches = re.finditer(r'limit\s*=\s*\{\s*vegetation\s*=\s*(\w+)\s*\}\s*add\s*=\s*(-?\d+\.?\d*)', block_content, re.DOTALL)
            for m in veg_matches:
                name = m.group(1)
                val = float(m.group(2))
                if name not in data["vegetation"]: data["vegetation"][name] = {}
                data["vegetation"][name][mod_key] = val

            # Parse Water/Static in this block
            water_checks = {
                "is_coastal": "coastal",
                "has_river": "river",
                "is_adjacent_to_lake": "lake"
            }
            for check, key in water_checks.items():
                water_match = re.search(rf'limit\s*=\s*\{{\s*{check}\s*=\s*yes\s*\}}\s*add\s*=\s*(-?\d+\.?\d*)', block_content, re.DOTALL)
                if water_match:
                    val = float(water_match.group(1))
                    if mod_key not in data["static"][key]: data["static"][key][mod_key] = 0.0
                    data["static"][key][mod_key] = val

            # Parse RGO Match Bonus
            rgo_matches = re.finditer(r'limit\s*=\s*\{[^}]*raw_material\s*=\s*(?:goods:)?(\w+)[^}]*\}\s*add\s*=\s*(-?\d+\.?\d*)', block_content, re.DOTALL)
            for m in rgo_matches:
                good_name = m.group(1)
                val = float(m.group(2))
                if good_name not in data["rgo"]: data["rgo"][good_name] = {}
                data["rgo"][good_name][mod_key] = val
            
            # Special case for OR blocks in RGO matches
            or_rgo_matches = re.finditer(r'limit\s*=\s*\{[^}]*OR\s*=\s*\{([^}]*)\}[^}]*\}\s*add\s*=\s*(-?\d+\.?\d*)', block_content, re.DOTALL)
            for m in or_rgo_matches:
                or_content = m.group(1)
                val = float(m.group(2))
                goods = re.findall(r'raw_material\s*=\s*(?:goods:)?(\w+)', or_content)
                for good in goods:
                    if good not in data["rgo"]: data["rgo"][good] = {}
                    data["rgo"][good][mod_key] = val

        return data

    def parse_building_caps(self, file_path):
        """
        Parses pp_building_caps.txt to extract base, dev_multiply, pop_multiply per script value.
        Returns: { "script_name": {"base": float, "dev": float, "pop": float}, ... }
        """
        if not os.path.exists(file_path):
            print(f"Warning: Building caps file not found: {file_path}")
            return {}

        with open(file_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()

        results = {}
        # Match script blocks: script_name = { ... }
        script_pattern = re.compile(r'(\w+)\s*=\s*\{', re.IGNORECASE)
        pos = 0

        while True:
            match = script_pattern.search(content, pos)
            if not match:
                break

            script_name = match.group(1)
            start_idx = match.end()
            depth = 1
            end_idx = start_idx
            while depth > 0 and end_idx < len(content):
                if content[end_idx] == '{':
                    depth += 1
                elif content[end_idx] == '}':
                    depth -= 1
                end_idx += 1

            block_content = content[start_idx:end_idx - 1]
            pos = end_idx

            # Extract base from add { desc = "BUILDING_LEVEL_BASE" value = X }
            base = 0.0
            base_match = re.search(
                r'desc\s*=\s*"BUILDING_LEVEL_BASE"[^}]*value\s*=\s*(-?\d+\.?\d*)',
                block_content, re.DOTALL
            )
            if base_match:
                base = float(base_match.group(1))

            # Extract dev multiply from add { value = development multiply = Y }
            dev = 0.0
            dev_match = re.search(
                r'value\s*=\s*development\s+multiply\s*=\s*(-?\d+\.?\d*)',
                block_content
            )
            if dev_match:
                dev = float(dev_match.group(1))

            # Extract pop multiply from add { value = population multiply = Z }
            pop = 0.0
            pop_match = re.search(
                r'value\s*=\s*population\s+multiply\s*=\s*(-?\d+\.?\d*)',
                block_content
            )
            if pop_match:
                pop = float(pop_match.group(1))

            results[script_name] = {"base": base, "dev": dev, "pop": pop}

        return results

    def parse_building_to_script(self, file_path):
        """
        Parses pp_building_adjustments.txt to map building_id to max_levels script name.
        Looks for REPLACE:building_id = { ... max_levels = script_name ... }.
        Returns: { "building_id": "script_name", ... }
        """
        if not os.path.exists(file_path):
            print(f"Warning: Building adjustments file not found: {file_path}")
            return {}

        with open(file_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()

        results = {}
        # Match REPLACE:entity = { or INJECT:entity = {
        block_pattern = re.compile(
            r'(?:REPLACE|INJECT|TRY_REPLACE|TRY_INJECT):(\w+)\s*=\s*\{',
            re.IGNORECASE
        )
        pos = 0

        while True:
            match = block_pattern.search(content, pos)
            if not match:
                break

            entity_name = match.group(1)
            start_idx = match.end()
            depth = 1
            end_idx = start_idx
            while depth > 0 and end_idx < len(content):
                if content[end_idx] == '{':
                    depth += 1
                elif content[end_idx] == '}':
                    depth -= 1
                end_idx += 1

            block_content = content[start_idx:end_idx - 1]
            pos = end_idx

            # Extract max_levels = script_name
            max_levels_match = re.search(
                r'max_levels\s*=\s*(\w+)',
                block_content
            )
            if max_levels_match:
                script_name = max_levels_match.group(1)
                results[entity_name] = script_name

        return results

    def get_all_data(self, mod_path, game_path=None):
        """
        Reads all mod files and returns a combined dictionary.
        Uses mod_path for all files; game_path as fallback for script_values if provided.
        """
        def _resolve_path(relative_path):
            """Try mod first, then game fallback."""
            mod_file = os.path.join(mod_path, relative_path)
            if os.path.exists(mod_file):
                return mod_file
            if game_path:
                game_file = os.path.join(game_path, relative_path)
                if os.path.exists(game_file):
                    return game_file
            return mod_file  # return anyway for error handling in parsers

        paths = {
            "rank": os.path.join(mod_path, "in_game/common/location_ranks/pp_location_rank_adjustments.txt"),
            "static": os.path.join(mod_path, "main_menu/common/static_modifiers/pp_location_modifier_adjustments.txt"),
            "precalc": os.path.join(mod_path, "in_game/common/script_values/pp_building_capacity_values.txt"),
            "caps": _resolve_path("in_game/common/script_values/pp_building_caps.txt"),
            "adjustments": _resolve_path("in_game/common/building_types/pp_building_adjustments.txt"),
        }
        
        rank_data = self.parse_file(paths["rank"], "rank_modifier")
        static_data = self.parse_file(paths["static"], "location_modifier")
        fixed_data = self.parse_precalc_file(paths["precalc"])
        caps_data = self.parse_building_caps(paths["caps"])
        building_to_script = self.parse_building_to_script(paths["adjustments"])
        
        data = {
            "climate": fixed_data["climate"],
            "topography": fixed_data["topography"],
            "vegetation": fixed_data["vegetation"],
            "rank": rank_data,
            "static": {**static_data, **fixed_data["static"]},
            "rgo": fixed_data["rgo"],
            "caps": caps_data,
            "building_to_script": building_to_script,
        }
        
        return data
