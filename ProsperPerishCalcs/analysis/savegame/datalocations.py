"""Build and save savegame payloads from EU5 saves.

Writes a versioned dict (format 2) to ``.pkl``: ``locations`` (merged with scope hierarchy),
``market_goods`` (per-market goods, flattened), and ``countries``.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from analysis.building_levels.building_analysis.utils import load_config
from analysis.savegame.loader import (
    get_countries_df,
    get_locations_df,
    get_market_goods_df,
    load_save,
    locations_df_from_pkl,
)
from core.data.location_data import LocationData
from core.data.population_capacity_data import (
    PopulationCapacityData,
    calculate_population_capacity,
)
from core.parser.path_resolver import PathResolver


def build_datalocations_df(save, location_data: LocationData) -> pd.DataFrame:
    """Build locations DataFrame merged with scope hierarchy only.

    Merges save runtime data with scope hierarchy (province, area, region, etc.).
    Uses hierarchy province as the canonical province column (no province_x/y conflict).
    Keeps pkls small; merge with full LocationData at analysis time if needed.
    """
    df_locs = get_locations_df(save)
    # Drop province from save to avoid province_x/province_y; use hierarchy province
    if "province" in df_locs.columns:
        df_locs = df_locs.drop(columns=["province"])

    df_scopes = location_data.get_merged_df()[
        ["location", "super_region", "macro_region", "region", "area", "province"]
    ].drop_duplicates(subset="location")

    df = df_locs.merge(
        df_scopes, left_on="slug", right_on="location", how="left"
    ).drop(columns=["location"])

    scope_cols = ["province", "area", "region", "macro_region", "super_region"]
    other_cols = [c for c in df.columns if c not in ["slug"] + scope_cols]
    return df[["slug"] + [c for c in scope_cols if c in df.columns] + other_cols]


def merge_saves_with_location_data(
    saves: dict[str, pd.DataFrame],
    path_resolver: PathResolver | None = None,
) -> dict[str, pd.DataFrame]:
    """Merge each save DataFrame with full LocationData. Call at analysis time when needed.

    Keeps pkls small; use this to add development, rank, food, topography, etc.
    """
    if path_resolver is None:
        config = load_config()
        path_resolver = PathResolver(
            config.get("game_path", ""), config.get("mod_path", "")
        )
    location_data = LocationData(path_resolver)
    location_data.load_all()
    df_loc = location_data.get_merged_df().drop_duplicates(subset="location")

    cap_data = PopulationCapacityData(path_resolver)
    cap_data.load_all()

    result = {}
    for label, obj in saves.items():
        df = locations_df_from_pkl(obj)
        if "slug" not in df.columns:
            result[label] = obj
            continue
        merged = df.merge(
            df_loc, left_on="slug", right_on="location", how="left",
            suffixes=("_pkl", "_loc"),
        )
        if "location" in merged.columns:
            merged = merged.drop(columns=["location"])

        # Recompute population_capacity using save's development (the only dynamic variable)
        dev_col = "development_pkl" if "development_pkl" in merged.columns else "development"
        merged["population_capacity"] = merged.apply(
            lambda row: calculate_population_capacity(
                row.get("topography") or "",
                row.get("vegetation") or "",
                row.get("climate") or "",
                (row.get("has_river") or "").lower() in ("yes", "true", "1"),
                float(row.get(dev_col, 0.0)),
                cap_data,
            ),
            axis=1,
        )
        # total_population / population_capacity (NaN when capacity is 0)
        pop_col = "total_population" if "total_population" in merged.columns else "population"
        merged["population_capacity_ratio"] = merged[pop_col].div(
            merged["population_capacity"].replace(0, pd.NA)
        )
        result[label] = merged
    return result


def create_datalocations_pkl(
    save_path: str | Path,
    output_path: str | Path,
    *,
    path_resolver: PathResolver | None = None,
) -> dict:
    """Load save, build payload, save to .pkl. Returns the payload dict (format 2)."""
    save = load_save(path=str(save_path))
    return create_datalocations_pkl_from_save(save, output_path, path_resolver)


def create_datalocations_pkl_from_save(
    save,
    output_path: str | Path,
    *,
    path_resolver: PathResolver | None = None,
) -> dict:
    """Build format-2 payload from an already-loaded save and write ``.pkl``."""
    if path_resolver is None:
        config = load_config()
        path_resolver = PathResolver(
            config.get("game_path", ""), config.get("mod_path", "")
        )
    location_data = LocationData(path_resolver)
    location_data.load_all()
    df = build_datalocations_df(save, location_data)
    payload = {
        "format": 2,
        "locations": df,
        "market_goods": get_market_goods_df(save),
        "countries": get_countries_df(save),
    }
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    pd.to_pickle(payload, output_path)
    return payload
