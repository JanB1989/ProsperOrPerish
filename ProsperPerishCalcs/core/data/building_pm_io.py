from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING

import pandas as pd

from .building_data import BuildingData, extract_unique_production_method_slots

if TYPE_CHECKING:
    from .goods_data import GoodsData


def _format_max_levels(ml: object) -> str:
    """Render building `max_levels` script value for display (literal, name, or JSON block)."""
    if ml is None:
        return ""
    if isinstance(ml, float) and pd.isna(ml):
        return ""
    if isinstance(ml, bool):
        return str(ml).lower()
    if isinstance(ml, int):
        return str(ml)
    if isinstance(ml, float):
        return str(int(ml)) if ml == int(ml) else str(ml)
    if isinstance(ml, str):
        return ml
    if isinstance(ml, dict):
        return json.dumps(ml, ensure_ascii=False, sort_keys=True)
    return str(ml)


def _ppm_dict_is_inline_pm_body(v: dict) -> bool:
    """True if this looks like a full PM script block rather than a bare flag."""
    if not v:
        return False
    if any(k in v for k in ("produced", "output", "category")):
        return True
    return len(v) >= 2


def iter_production_methods_for_building(
    building_name: str,
    building_def: dict | None,
    building_data: BuildingData,
    resolve_pm: Callable[[str], dict | None] | None = None,
) -> Iterator[tuple[str, dict]]:
    """
    Yield unique (production_method_name, pm_def) for one building after resolving
    external `possible_production_methods` references.

    Order: all `unique_production_methods` slots first, then `possible_production_methods`.
    Duplicate (building_name, pm_name) pairs are skipped (first wins).

    ``resolve_pm`` resolves external PM ids (default: merged game+mod ``get_production_method``).
    Use ``building_data.get_vanilla_production_method`` for vanilla-only resolution.
    """
    if not building_def:
        return
    if resolve_pm is None:
        resolve_pm = building_data.get_production_method

    seen: set[tuple[str, str]] = set()

    def _emit(pm_name: str, pm_def: dict | None) -> Iterator[tuple[str, dict]]:
        if not isinstance(pm_def, dict):
            return
        key = (building_name, pm_name)
        if key in seen:
            return
        seen.add(key)
        yield (pm_name, pm_def)

    for slot in extract_unique_production_method_slots(building_def):
        for pm_name, inner in slot.items():
            yield from _emit(pm_name, inner)

    ppm = building_def.get("possible_production_methods")
    if ppm is None or (isinstance(ppm, float) and pd.isna(ppm)):
        return

    if isinstance(ppm, str):
        yield from _emit(ppm, resolve_pm(ppm))
        return

    if isinstance(ppm, list):
        for item in ppm:
            if isinstance(item, str):
                yield from _emit(item, resolve_pm(item))
            elif isinstance(item, dict):
                for pm_name, pm_body in item.items():
                    if isinstance(pm_body, dict) and pm_body:
                        yield from _emit(pm_name, pm_body)
        return

    if isinstance(ppm, dict):
        for pm_name, v in ppm.items():
            if isinstance(v, dict) and v and _ppm_dict_is_inline_pm_body(v):
                yield from _emit(pm_name, v)
            else:
                yield from _emit(pm_name, resolve_pm(pm_name))


def build_pm_io_matrix(
    building_data: BuildingData,
    goods_data: GoodsData,
    merged: bool = True,
) -> pd.DataFrame:
    """
    One row per (building, production_method) where the PM has a registered trade-good
    `produced` and positive resolved `output`. Inputs are trade-good keys only
    (see `pm_trade_good_inputs` filtered by goods index).

    Columns: building, max_levels, production_method, sorted i_<good>, sorted o_<good> (all goods).

    Parameters
    ----------
    merged
        If True (default), use merged vanilla+mod buildings, production methods, and goods
        (active mod loadout). If False, use vanilla game definitions only for buildings,
        external PM lookups, and goods columns.
    """
    if merged:
        goods_index = goods_data.modded_df.index
        building_names = building_data.modded_df.index.astype(str)
        get_building = building_data.get_building
        resolve_pm = building_data.get_production_method
    else:
        goods_index = goods_data.vanilla_df.index
        building_names = building_data.vanilla_df.index.astype(str)
        get_building = building_data.get_vanilla_building
        resolve_pm = building_data.get_vanilla_production_method

    good_ids = sorted(goods_index.astype(str))
    col_i = [f"i_{g}" for g in good_ids]
    col_o = [f"o_{g}" for g in good_ids]

    rows: list[dict] = []

    for building_name in building_names:
        bdef = get_building(building_name)
        if not bdef:
            continue
        max_levels_s = _format_max_levels(bdef.get("max_levels"))
        for pm_name, pm_def in iter_production_methods_for_building(
            building_name, bdef, building_data, resolve_pm=resolve_pm
        ):
            produced = pm_def.get("produced")
            if produced is None or (isinstance(produced, float) and pd.isna(produced)):
                continue
            if not isinstance(produced, str):
                continue
            if produced not in goods_index:
                continue

            out_amt = building_data._resolve_value(pm_def.get("output"))
            if pd.isna(out_amt) or out_amt <= 0.0:
                continue

            raw_inputs = building_data.pm_trade_good_inputs(pm_def)
            inputs = {
                k: v
                for k, v in raw_inputs.items()
                if k in goods_index
            }

            row: dict = {
                "building": building_name,
                "max_levels": max_levels_s,
                "production_method": pm_name,
            }
            for g in good_ids:
                row[f"i_{g}"] = float(inputs.get(g, 0.0))
                row[f"o_{g}"] = float(out_amt) if g == produced else 0.0
            rows.append(row)

    if not rows:
        return pd.DataFrame(columns=["building", "max_levels", "production_method", *col_i, *col_o])

    df = pd.DataFrame(rows)
    ordered = ["building", "max_levels", "production_method", *col_i, *col_o]
    return df[[c for c in ordered if c in df.columns]]
