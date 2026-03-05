import pandas as pd
from .base_data import DataModule

class DefinesData(DataModule):
    """Module for parsing and accessing game defines (vanilla and modded)."""

    def __init__(self, path_resolver):
        super().__init__(path_resolver)
        self.vanilla_defines = {}
        self.modded_defines = {}

    def load_all(self):
        """Loads all defines from vanilla and mod paths."""
        # Note: Defines are usually in common/defines, but user specified loading_screen/common/defines
        # We will use the relative path provided by the user.
        relative_path = "loading_screen/common/defines"
        
        # 1. Load vanilla defines
        self.vanilla_defines = self.load_vanilla_only(relative_path)
        
        # 2. Load modded defines
        mod_defines = self.load_mod_only(relative_path)
        
        # 3. Merge modded into vanilla
        self.modded_defines = self._merge_data(self.vanilla_defines, mod_defines)
        
        return self.modded_defines

    def get_define(self, category, key, default=None):
        """Returns a modded define value."""
        cat_data = self.modded_defines.get(category, {})
        return cat_data.get(key, default)

    def get_vanilla_define(self, category, key, default=None):
        """Returns a vanilla define value."""
        cat_data = self.vanilla_defines.get(category, {})
        return cat_data.get(key, default)
