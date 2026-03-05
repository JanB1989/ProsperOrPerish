"""
Parse country setup to get starting societal values (spiritualist_vs_humanist, aristocracy_vs_plutocracy)
per country. Resolves include templates and country overrides.
"""
import os
import pandas as pd
from .base_data import DataModule


class CountrySetupData(DataModule):
    """Parses country setup for starting societal values per country."""

    def __init__(self, path_resolver):
        super().__init__(path_resolver)
        self.societal_values_df = pd.DataFrame()  # tag, spiritualist_vs_humanist, aristocracy_vs_plutocracy

    def _load_template(self, name):
        """Load and merge a template by name (main_menu/setup/templates/{name}.txt)."""
        rel = f"main_menu/setup/templates/{name}.txt"
        paths = self.path_resolver.resolve_path(rel)
        merged = {}
        for path in paths:
            if os.path.exists(path):
                try:
                    data = self.parser.parse(path)
                    merged = self._deep_merge(merged, data)
                except Exception as e:
                    raise type(e)(f"Error parsing template {path}: {str(e)}") from e
        return merged

    def _extract_societal_values(self, data):
        """Extract spiritualist_vs_humanist and aristocracy_vs_plutocracy from a parsed block."""
        gov = data.get("government") if isinstance(data, dict) else None
        if not isinstance(gov, dict):
            return None, None
        try:
            sv = float(gov.get("spiritualist_vs_humanist"))
        except (TypeError, ValueError):
            sv = None
        try:
            av = float(gov.get("aristocracy_vs_plutocracy"))
        except (TypeError, ValueError):
            av = None
        return sv, av

    def load_all(self):
        """Load country setup and build societal values per tag."""
        setup_data = self.load_directory("main_menu/setup/start")
        countries_block = setup_data.get("countries") or {}
        inner = countries_block.get("countries") if isinstance(countries_block, dict) else {}
        if not isinstance(inner, dict):
            self.societal_values_df = pd.DataFrame(columns=["owner_tag", "spiritualist_vs_humanist", "aristocracy_vs_plutocracy"])
            return self.societal_values_df

        rows = []
        for tag, country_data in inner.items():
            if not isinstance(country_data, dict):
                continue
            accumulated = {}
            # Merge includes in order (each later overrides earlier)
            includes = country_data.get("include")
            if includes is not None:
                if isinstance(includes, str):
                    includes = [includes]
                for inc in includes:
                    if isinstance(inc, str):
                        template = self._load_template(inc)
                        accumulated = self._deep_merge(accumulated, template)
            # Country's own block overrides
            accumulated = self._deep_merge(accumulated, country_data)
            sv, av = self._extract_societal_values(accumulated)
            capital = accumulated.get("capital")
            if isinstance(capital, str) and ":" in capital:
                capital = capital.split(":")[-1]  # e.g. location_rank:stockholm -> stockholm
            elif not isinstance(capital, str):
                capital = None
            rows.append({
                "owner_tag": tag,
                "spiritualist_vs_humanist": sv if sv is not None else pd.NA,
                "aristocracy_vs_plutocracy": av if av is not None else pd.NA,
                "capital": capital if capital else pd.NA,
            })

        self.societal_values_df = pd.DataFrame(rows)
        return self.societal_values_df

    def get_societal_values_df(self):
        """Returns DataFrame: owner_tag, spiritualist_vs_humanist, aristocracy_vs_plutocracy, capital."""
        if self.societal_values_df.empty:
            self.load_all()
        return self.societal_values_df
