"""Savegame analysis module for EU5. Load savegames and extract data to pandas."""

from analysis.savegame.datalocations import (
    build_datalocations_df,
    create_datalocations_pkl,
    create_datalocations_pkl_from_save,
    merge_saves_with_location_data,
)
from analysis.savegame.loader import (
    build_save_comparison_df,
    get_buildings_df,
    get_global_benchmark_df,
    get_countries_df,
    get_latest_save_path,
    get_locations_df,
    get_market_food_df,
    get_market_goods_df,
    get_religion_data,
    inspect_savegame,
    load_save,
    locations_df_from_pkl,
)
from analysis.savegame.processor import get_pkl_dir, resolve_pkl_dir, run_watcher

__all__ = [
    "build_datalocations_df",
    "create_datalocations_pkl_from_save",
    "build_save_comparison_df",
    "get_global_benchmark_df",
    "create_datalocations_pkl",
    "get_buildings_df",
    "get_countries_df",
    "get_latest_save_path",
    "get_locations_df",
    "get_market_food_df",
    "get_market_goods_df",
    "get_pkl_dir",
    "locations_df_from_pkl",
    "merge_saves_with_location_data",
    "get_religion_data",
    "inspect_savegame",
    "load_save",
    "resolve_pkl_dir",
    "run_watcher",
]
