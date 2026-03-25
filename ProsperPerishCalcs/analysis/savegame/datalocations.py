"""Build and save savegame payloads from EU5 saves.

Writes a versioned dict (format 2) to ``.pkl``: ``locations`` (merged with scope hierarchy),
``buildings`` (from ``get_buildings_df``), ``market_goods`` (per-market trade goods, flattened),
``market_food`` (abstract food market per market), and ``countries``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd

from analysis.building_levels.building_analysis.utils import load_config
from analysis.savegame.loader import (
    buildings_df_from_pkl,
    get_buildings_df,
    get_countries_df,
    get_locations_df,
    get_market_food_df,
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


def _sanitize_building_slug_for_column(slug: str) -> str:
    s = str(slug).strip()
    if not s:
        return "unknown"
    return "".join(c if (c.isalnum() or c == "_") else "_" for c in s)


def merge_building_counts_into_locations(
    locations_df: pd.DataFrame,
    buildings_df: pd.DataFrame,
    building_slugs: tuple[str, ...],
    *,
    count_mode: Literal["levels", "instances"] = "levels",
) -> pd.DataFrame:
    """Attach per-location building totals for selected types (columns ``bldg_<slug>``).

    Joins on ``location_id``. Missing locations get 0. When ``count_mode`` is ``levels``,
    sums ``level`` per (location, type); otherwise counts rows (building instances).

    Column names use :func:`_sanitize_building_slug_for_column`. If a name would collide
    with an existing column, a ``_2``, ``_3``, ... suffix is appended.
    """
    if not building_slugs or locations_df.empty:
        return locations_df
    if "location_id" not in locations_df.columns:
        return locations_df

    slug_set = frozenset(building_slugs)
    if buildings_df.empty or "slug" not in buildings_df.columns:
        out = locations_df.copy()
        existing = set(out.columns)
        for s in building_slugs:
            col = _reserve_bldg_column_name(s, existing)
            out[col] = 0.0
        return out

    sub = buildings_df[buildings_df["slug"].isin(slug_set)].copy()
    sub = sub.dropna(subset=["location_id"])

    if count_mode not in ("levels", "instances"):
        raise ValueError(
            "count_mode must be 'levels' or 'instances'; "
            f"got {count_mode!r}"
        )

    if sub.empty:
        out = locations_df.copy()
        existing = set(out.columns)
        for s in building_slugs:
            col = _reserve_bldg_column_name(s, existing)
            out[col] = 0.0
        return out

    if count_mode == "levels" and "level" in sub.columns:
        sub["level"] = pd.to_numeric(sub["level"], errors="coerce").fillna(0)
        agg = sub.groupby(["location_id", "slug"], dropna=False)["level"].sum()
    else:
        agg = sub.groupby(["location_id", "slug"], dropna=False).size()

    wide = agg.unstack(level=1, fill_value=0)
    wide = wide.fillna(0)

    out = locations_df.copy()
    existing = set(out.columns)
    for slug in building_slugs:
        col_name = _reserve_bldg_column_name(slug, existing)
        if slug in wide.columns:
            series = wide[slug].reindex(out["location_id"]).fillna(0).astype(float)
        else:
            series = pd.Series(0.0, index=out.index)
        out[col_name] = series.values
        existing.add(col_name)

    return out


def _reserve_bldg_column_name(slug: str, existing: set[str]) -> str:
    base = f"bldg_{_sanitize_building_slug_for_column(slug)}"
    name = base
    n = 2
    while name in existing:
        name = f"{base}_{n}"
        n += 1
    return name


def collect_building_slugs_union_from_saves(
    saves: dict[str, pd.DataFrame | dict],
) -> tuple[str, ...]:
    """Return sorted unique building-type slugs appearing in any snapshot's buildings table."""
    all_slugs: set[str] = set()
    for obj in saves.values():
        bdf = buildings_df_from_pkl(obj) if isinstance(obj, dict) else pd.DataFrame()
        if bdf.empty or "slug" not in bdf.columns:
            continue
        for s in bdf["slug"].dropna().astype(str):
            t = s.strip()
            if t:
                all_slugs.add(t)
    return tuple(sorted(all_slugs))


def merge_saves_with_location_data(
    saves: dict[str, pd.DataFrame | dict],
    path_resolver: PathResolver | None = None,
    *,
    building_slugs: tuple[str, ...] | None = None,
    include_all_building_types: bool = False,
    building_count_mode: Literal["levels", "instances"] = "levels",
) -> dict[str, pd.DataFrame]:
    """Merge each save DataFrame with full LocationData. Call at analysis time when needed.

    Keeps pkls small; use this to add development, rank, food, topography, etc.

    When ``building_slugs`` is non-empty, each merged locations frame also gets
    ``bldg_<type>`` columns from that snapshot's ``buildings`` payload (see
    :func:`merge_building_counts_into_locations`).

    When ``include_all_building_types`` is True, ``building_slugs`` is ignored and the
    union of all slugs across every payload is used so every snapshot gets the same
    set of columns (zeros where a type does not exist yet in that year).
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

    if include_all_building_types:
        resolved_building_slugs = collect_building_slugs_union_from_saves(saves)
    else:
        resolved_building_slugs = tuple(building_slugs) if building_slugs else ()

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

        if resolved_building_slugs:
            bdf = buildings_df_from_pkl(obj) if isinstance(obj, dict) else pd.DataFrame()
            merged = merge_building_counts_into_locations(
                merged,
                bdf,
                resolved_building_slugs,
                count_mode=building_count_mode,
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
        "buildings": get_buildings_df(save),
        "market_goods": get_market_goods_df(save),
        "market_food": get_market_food_df(save),
        "countries": get_countries_df(save),
    }
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    pd.to_pickle(payload, output_path)
    return payload
