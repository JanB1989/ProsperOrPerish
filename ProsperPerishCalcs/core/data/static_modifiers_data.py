"""
Parse static_modifiers/location.txt to extract location_base_values.
Provides local_X_desired_pop_scaled for base location (scaled modifiers).
"""
from .base_data import DataModule

_BASE_SCALED_KEYS = (
    ("clergy", "local_clergy_desired_pop_scaled"),
    ("nobles", "local_nobles_desired_pop_scaled"),
)


class StaticModifiersData(DataModule):
    """Parses location_base_values for desired_pop_scaled modifiers."""

    def __init__(self, path_resolver):
        super().__init__(path_resolver)
        self.base_scaled = {}  # pop_type -> value (fraction)

    def load_all(self):
        """Load static_modifiers and extract location_base_values scaled modifiers."""
        data = self.load_directory("main_menu/common/static_modifiers")
        base = data.get("location_base_values")
        if not isinstance(base, dict):
            self.base_scaled = {p: 0.0 for p, _ in _BASE_SCALED_KEYS}
            return self.base_scaled

        self.base_scaled = {}
        for pop_type, key in _BASE_SCALED_KEYS:
            try:
                self.base_scaled[pop_type] = float(base.get(key, 0))
            except (TypeError, ValueError):
                self.base_scaled[pop_type] = 0.0

        return self.base_scaled

    def get_base_scaled(self, pop_type):
        """Returns the base scaled value for a pop type (clergy, nobles). Default 0."""
        if not self.base_scaled:
            self.load_all()
        return self.base_scaled.get(pop_type, 0.0)
