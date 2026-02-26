import os
from ..parser.paradox_parser import ParadoxParser

class DataModule:
    """Base class for data modules that merge vanilla and mod data."""

    def __init__(self, path_resolver):
        self.path_resolver = path_resolver
        self.parser = ParadoxParser()
        self.data = {}

    def _merge_data(self, vanilla_data, mod_data):
        """
        Merges mod data into vanilla data based on INJECT/REPLACE rules.
        Treats vanilla as the base truth (Gospel).
        """
        merged = vanilla_data.copy()
        
        for key, value in mod_data.items():
            # Handle explicit prefixes
            if key.startswith("TRY_REPLACE:") or key.startswith("REPLACE:"):
                entity_name = key.split(":", 1)[1]
                merged[entity_name] = value
            elif key.startswith("TRY_INJECT:") or key.startswith("INJECT:"):
                entity_name = key.split(":", 1)[1]
                if entity_name in merged:
                    merged[entity_name] = self._deep_merge(merged[entity_name], value)
                else:
                    merged[entity_name] = value
            else:
                # No prefix: If it exists in vanilla, we deep merge (Vanilla as Gospel)
                # unless it's a completely new entity.
                if key in merged:
                    merged[key] = self._deep_merge(merged[key], value)
                else:
                    merged[key] = value
                
        return merged

    def _deep_merge(self, base, override):
        """Recursively merges two structures."""
        if isinstance(base, dict) and isinstance(override, dict):
            new_dict = base.copy()
            for k, v in override.items():
                if k in new_dict:
                    new_dict[k] = self._deep_merge(new_dict[k], v)
                else:
                    new_dict[k] = v
            return new_dict
        elif isinstance(base, list) and isinstance(override, list):
            # For lists, we typically append or replace depending on context.
            # In Paradox scripts, merging lists usually means appending.
            return base + [x for x in override if x not in base]
        else:
            # Simple value: override the base
            return override

    def load_directory(self, relative_dir):
        """Loads and merges all files in a mirrored directory structure."""
        vanilla_data = self.load_vanilla_only(relative_dir)
        mod_data = self.load_mod_only(relative_dir)
        return self._merge_data(vanilla_data, mod_data)

    def load_vanilla_only(self, relative_dir):
        """Loads only vanilla files for a directory using deep merge."""
        vanilla_files = self.path_resolver.get_vanilla_files(relative_dir)
        all_data = {}
        for f in vanilla_files:
            try:
                file_data = self.parser.parse(f)
                # Use deep merge to aggregate data from multiple files in the same folder
                all_data = self._deep_merge(all_data, file_data)
            except Exception as e:
                # No silent errors
                raise type(e)(f"Error parsing vanilla file {f}: {str(e)}") from e
        return all_data

    def load_mod_only(self, relative_dir):
        """Loads only mod files for a directory using deep merge."""
        mod_files = self.path_resolver.get_mod_files(relative_dir)
        all_data = {}
        for f in mod_files:
            try:
                file_data = self.parser.parse(f)
                # Use deep merge to aggregate data from multiple files in the same folder
                all_data = self._deep_merge(all_data, file_data)
            except Exception as e:
                # No silent errors
                raise type(e)(f"Error parsing mod file {f}: {str(e)}") from e
        return all_data
