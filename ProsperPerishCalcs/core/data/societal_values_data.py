"""
Parse in_game/common/societal_values to extract base scaled values for desired_pop.
Provides global_clergy_city_desired_pop_scaled (spiritualist) and
global_nobles_city_desired_pop_scaled (aristocracy) from left_modifier.
"""
from .base_data import DataModule


class SocietalValuesData(DataModule):
    """Parses societal values for desired_pop_scaled modifiers (clergy, nobles)."""

    def __init__(self, path_resolver):
        super().__init__(path_resolver)
        self.clergy_city_base_scaled = 0.0
        self.nobles_city_base_scaled = 0.0
        self._loaded = False

    def load_all(self):
        """Load societal_values and extract clergy/nobles city scaled base values."""
        data = self.load_directory("in_game/common/societal_values")

        # spiritualist left = global_clergy_city_desired_pop_scaled
        spiritualist = data.get("spiritualist_vs_humanist")
        if isinstance(spiritualist, dict):
            left = spiritualist.get("left_modifier")
            if isinstance(left, dict):
                try:
                    self.clergy_city_base_scaled = float(left.get("global_clergy_city_desired_pop_scaled", 0))
                except (TypeError, ValueError):
                    pass

        # aristocracy left = global_nobles_city_desired_pop_scaled
        aristocracy = data.get("aristocracy_vs_plutocracy")
        if isinstance(aristocracy, dict):
            left = aristocracy.get("left_modifier")
            if isinstance(left, dict):
                try:
                    self.nobles_city_base_scaled = float(left.get("global_nobles_city_desired_pop_scaled", 0))
                except (TypeError, ValueError):
                    pass

        self._loaded = True
        return self

    def get_effective_clergy_city_scaled(self, spiritualist_vs_humanist):
        """Effective clergy city scaled = base * |sv|/100 when sv<0 (left/spiritualist), else 0.
        Negative values scale the left modifier: -60 = 60% of max, -100 = 100%."""
        if not self._loaded:
            self.load_all()
        try:
            sv = float(spiritualist_vs_humanist)
        except (TypeError, ValueError):
            return 0.0
        # <0 = left (spiritualist), >0 = right (humanist). Left fraction = max(0, -sv)/100
        factor = max(0.0, min(1.0, max(0.0, -sv) / 100.0))
        return self.clergy_city_base_scaled * factor

    def get_effective_nobles_city_scaled(self, aristocracy_vs_plutocracy):
        """Effective nobles city scaled = base * |av|/100 when av<0 (left/aristocracy), else 0.
        Negative values scale the left modifier: -60 = 60% of max, -100 = 100%."""
        if not self._loaded:
            self.load_all()
        try:
            av = float(aristocracy_vs_plutocracy)
        except (TypeError, ValueError):
            return 0.0
        # <0 = left (aristocracy), >0 = right (plutocracy). Left fraction = max(0, -av)/100
        factor = max(0.0, min(1.0, max(0.0, -av) / 100.0))
        return self.nobles_city_base_scaled * factor
