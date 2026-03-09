"""Savegame analysis module for EU5. Load savegames and extract data to pandas."""

from analysis.savegame.loader import (
    get_buildings_df,
    get_countries_df,
    get_latest_save_path,
    get_locations_df,
    load_save,
)

__all__ = [
    "get_buildings_df",
    "get_countries_df",
    "get_latest_save_path",
    "get_locations_df",
    "load_save",
]
