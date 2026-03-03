"""
Parse location_ranks (in_game/common/location_ranks) to extract local_X_desired_pop.
Builds a DataFrame with pop_type as rows and location_rank as columns.
Peasants = 1 - sum(other desired_pop).
"""
import pandas as pd
from .base_data import DataModule

_LOCATION_RANKS = ("rural_settlement", "town", "city")

# Explicit desired_pop keys; peasants = 1 - sum(others)
_DESIRED_POP_KEYS = (
    ("burghers", "local_burghers_desired_pop"),
    ("laborers", "local_laborers_desired_pop"),
    ("soldiers", "local_soldiers_desired_pop"),
    ("nobles", "local_nobles_desired_pop"),
    ("clergy", "local_clergy_desired_pop"),
)


class LocationRanksData(DataModule):
    """Parses location_ranks to get desired pop fractions per rank."""

    def __init__(self, path_resolver):
        super().__init__(path_resolver)
        self.desired_pop_df = pd.DataFrame()

    def load_all(self):
        """Load location_ranks and build desired_pop DataFrame."""
        ranks_data = self.load_directory("in_game/common/location_ranks")
        data = {}  # rank -> { pop_type: value }

        for rank_name in _LOCATION_RANKS:
            rank_block = ranks_data.get(rank_name)
            rank_mod = rank_block.get("rank_modifier") if isinstance(rank_block, dict) else None
            if not isinstance(rank_mod, dict):
                data[rank_name] = {pop: 0.0 for pop, _ in _DESIRED_POP_KEYS}
                data[rank_name]["peasants"] = 1.0
                continue

            row = {}
            for pop_type, key in _DESIRED_POP_KEYS:
                try:
                    # Fixed: adds raw count (0.015 = add 0.015 nobles), NOT a fraction - no /100
                    row[pop_type] = float(rank_mod.get(key, 0))
                except (TypeError, ValueError):
                    row[pop_type] = 0.0
            row["peasants"] = max(0.0, 1.0 - sum(row.values()))
            data[rank_name] = row

        all_pop_types = [p for p, _ in _DESIRED_POP_KEYS] + ["peasants"]
        rows = [{"pop_type": p, **{r: data[r][p] for r in _LOCATION_RANKS}} for p in all_pop_types]
        self.desired_pop_df = pd.DataFrame(rows).set_index("pop_type")
        return self.desired_pop_df

    def get_desired_pop_df(self):
        """Returns DataFrame: index=pop_type, columns=rural_settlement|town|city."""
        if self.desired_pop_df.empty:
            self.load_all()
        return self.desired_pop_df
