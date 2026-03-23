"""
Parse population capacity modifiers from game files.

Extracts local_population_capacity (additive) and local_population_capacity_modifier
(multiplicative) from:
- static_modifiers/location.txt: development, river_flowing_through
- topography, vegetation, climate (vanilla + mod TRY_INJECT)
"""

from __future__ import annotations

from .base_data import DataModule

_CAPACITY_ADD = "local_population_capacity"
_CAPACITY_MOD = "local_population_capacity_modifier"


def _float(val, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _extract_from_block(block, add_key: str = _CAPACITY_ADD, mod_key: str = _CAPACITY_MOD) -> tuple[float, float]:
    """Extract additive and multiplicative values from a modifier block (dict or nested)."""
    add_val = default_add = 0.0
    mod_val = default_mod = 0.0

    def walk(obj):
        nonlocal add_val, mod_val
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == add_key:
                    add_val = _float(v, add_val)
                elif k == mod_key:
                    mod_val = _float(v, mod_val)
                else:
                    walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(block)
    return add_val, mod_val


class PopulationCapacityData(DataModule):
    """Parses population capacity modifiers from topography, vegetation, climate, river, development."""

    def __init__(self, path_resolver):
        super().__init__(path_resolver)
        self.development_add_per_point = 0.0
        self.development_modifier_per_point = 0.0
        self.river_add = 0.0
        self.river_modifier = 0.0
        self.topography: dict[str, tuple[float, float]] = {}
        self.vegetation: dict[str, tuple[float, float]] = {}
        self.climate: dict[str, tuple[float, float]] = {}

    def load_all(self):
        """Load and parse all population capacity sources."""
        # 1. Static modifiers: development, river
        static = self.load_directory("main_menu/common/static_modifiers")

        dev_block = static.get("development")
        if isinstance(dev_block, dict):
            add, mod = _extract_from_block(dev_block)
            self.development_add_per_point = add
            self.development_modifier_per_point = mod
        elif isinstance(dev_block, list):
            for b in dev_block:
                if isinstance(b, dict):
                    add, mod = _extract_from_block(b)
                    self.development_add_per_point = add
                    self.development_modifier_per_point = mod
                    break

        river_block = static.get("river_flowing_through")
        if isinstance(river_block, dict):
            self.river_add, self.river_modifier = _extract_from_block(river_block)
        elif isinstance(river_block, list):
            for b in river_block:
                if isinstance(b, dict):
                    self.river_add, self.river_modifier = _extract_from_block(b)
                    break

        # 2. Topography
        topo_data = self.load_directory("in_game/common/topography")
        self.topography = self._extract_per_type(topo_data)

        # 3. Vegetation
        veg_data = self.load_directory("in_game/common/vegetation")
        self.vegetation = self._extract_per_type(veg_data)

        # 4. Climate
        climate_data = self.load_directory("in_game/common/climates")
        self.climate = self._extract_per_type(climate_data)

        return self

    def _extract_per_type(self, data: dict) -> dict[str, tuple[float, float]]:
        """Extract (add, modifier) per type from topography/vegetation/climate data."""
        result = {}
        for key, block in data.items():
            # Skip TRY_INJECT: prefix - after merge the key is the entity name
            if key.startswith(("TRY_INJECT:", "TRY_REPLACE:", "INJECT:", "REPLACE:")):
                continue
            if not isinstance(block, dict):
                continue
            loc_mod = block.get("location_modifier")
            if loc_mod is None:
                continue
            if isinstance(loc_mod, list):
                add_tot, mod_tot = 0.0, 0.0
                for lm in loc_mod:
                    if isinstance(lm, dict):
                        a, m = _extract_from_block(lm)
                        add_tot += a
                        mod_tot += m
                result[key] = (add_tot, mod_tot)
            else:
                result[key] = _extract_from_block(loc_mod)
        return result

    def get_topography(self, name: str) -> tuple[float, float]:
        """(add, modifier) for topography type. (0, 0) if unknown."""
        return self.topography.get(name, (0.0, 0.0))

    def get_vegetation(self, name: str) -> tuple[float, float]:
        """(add, modifier) for vegetation type. (0, 0) if unknown."""
        return self.vegetation.get(name, (0.0, 0.0))

    def get_climate(self, name: str) -> tuple[float, float]:
        """(add, modifier) for climate type. (0, 0) if unknown."""
        return self.climate.get(name, (0.0, 0.0))


def calculate_population_capacity(
    topography: str | None,
    vegetation: str | None,
    climate: str | None,
    has_river: bool,
    development: float,
    capacity_data: PopulationCapacityData,
) -> float:
    """Compute population capacity for a location.

    Formula: sum(additive) * (1 + sum(modifier))
    - additive from topography, vegetation, climate, river, development
    - modifier from topography, vegetation, climate, river, development
    """
    if not capacity_data.topography and not capacity_data.vegetation:
        capacity_data.load_all()

    add_total = 0.0
    mod_total = 0.0

    if topography:
        a, m = capacity_data.get_topography(topography)
        add_total += a
        mod_total += m

    if vegetation:
        a, m = capacity_data.get_vegetation(vegetation)
        add_total += a
        mod_total += m

    if climate:
        a, m = capacity_data.get_climate(climate)
        add_total += a
        mod_total += m

    if has_river:
        add_total += capacity_data.river_add
        mod_total += capacity_data.river_modifier

    # Development: scaled by development (0-100)
    dev = max(0.0, min(100.0, development))
    add_total += capacity_data.development_add_per_point * dev
    mod_total += capacity_data.development_modifier_per_point * dev

    # additive * (1 + modifier)
    mult = 1.0 + mod_total
    return max(0.0, add_total * mult)
