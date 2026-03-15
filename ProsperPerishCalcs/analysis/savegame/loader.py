"""Loader for EU5 savegames. Uses pyeu5 when available, falls back to native text parse."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from analysis.building_levels.building_analysis.utils import load_config


def _is_text_format_save(path: str | Path) -> bool:
    """Return True if the save file is text format (debug mode, parseable without Rakaly)."""
    path = Path(path)
    if not path.exists() or not path.is_file():
        return False
    try:
        head = path.read_bytes()[:128]
    except OSError:
        return False
    if not head.startswith(b"SAV"):
        return False
    # After first newline, body should start with metadata= or similar Paradox script
    if b"\n" not in head:
        return False
    body_start = head.index(b"\n") + 1
    body = head[body_start:].lstrip()
    return body.startswith(b"metadata=") or body.startswith(b"{")


def _parse_text_save(path: str | Path) -> dict:
    """Parse a text-format EU5 save with ParadoxParser. Skips header line."""
    path = Path(path)
    content = path.read_text(encoding="utf-8", errors="replace")
    first_nl = content.index("\n")
    body = content[first_nl + 1 :]
    from core.parser.paradox_parser import ParadoxParser

    parser = ParadoxParser()
    fd, tmp_path = tempfile.mkstemp(suffix=".txt", text=True)
    try:
        with open(fd, "w", encoding="utf-8") as f:
            f.write(body)
        return parser.parse(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


class _DictWrapper:
    """Minimal wrapper so getattr(obj, 'name') returns data.get('name'). Attributes can be set."""

    def __init__(self, data: dict, id_=None):
        self._data = data or {}
        self._id = id_

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return self._data.get(name)


class SaveAdapter:
    """Adapter for natively parsed text saves. Provides same interface as pyeu5 Save for get_*_df."""

    def __init__(self, data: dict):
        self._data = data
        self._countries = self._build_countries()
        self._locations = self._build_locations()
        self._buildings = self._build_buildings()

    @property
    def name(self) -> str:
        meta = self._get_metadata()
        return meta.get("playthrough_name") or meta.get("save_label") or "Unknown"

    @property
    def game_date(self):
        meta = self._get_metadata()
        date_val = meta.get("date", "1337.1.1")
        return SimpleNamespace(year=1337, month=1, day=1) if date_val else None

    def _get_metadata(self) -> dict:
        m = self._data.get("metadata")
        return m if isinstance(m, dict) else {}

    def _build_countries(self) -> dict:
        result = {}
        countries = self._data.get("countries") or {}
        db = countries.get("database") if isinstance(countries, dict) else {}
        if not isinstance(db, dict):
            return result
        for sid, cdata in db.items():
            if cdata == "none" or not isinstance(cdata, dict):
                continue
            try:
                cid = int(sid)
            except (ValueError, TypeError):
                continue
            result[cid] = _DictWrapper(cdata, id_=cid)
            result[cid].name = (
                cdata.get("country_name") or cdata.get("definition")
                or cdata.get("name") or cdata.get("tag") or str(cid)
            )
            result[cid].population = _float(cdata.get("population"), 0.0)
            econ = cdata.get("economy") if isinstance(cdata.get("economy"), dict) else {}
            mg = econ.get("monthly_gold")
            result[cid].gold = _float(
                cdata.get("gold") or (mg[-1] if isinstance(mg, list) and mg else mg),
                0.0,
            )
            result[cid].stability = _float(cdata.get("stability"), 0.0)
            result[cid].prestige = _float(cdata.get("prestige"), 0.0)
            result[cid].monthly_income = _float(
                cdata.get("monthly_income") or econ.get("income"), 0.0
            )
            gov = cdata.get("government") if isinstance(cdata.get("government"), dict) else {}
            result[cid].government_type = str(
                cdata.get("government_type") or gov.get("type", "")
            )
        return result

    def _build_locations(self) -> dict:
        result = {}
        loc_block = self._data.get("locations") or {}
        locs = loc_block.get("locations") if isinstance(loc_block, dict) else loc_block
        if not isinstance(locs, dict):
            return result
        compat = self._get_metadata().get("compatibility") or {}
        comp_locs = compat.get("locations") if isinstance(compat, dict) else None
        mm_db = (self._data.get("market_manager") or {}).get("database") or {}
        prov_db = (self._data.get("provinces") or {}).get("database") or {}
        if not isinstance(mm_db, dict):
            mm_db = {}
        if not isinstance(prov_db, dict):
            prov_db = {}
        for sid, ldata in sorted(locs.items(), key=lambda x: (int(x[0]) if str(x[0]).replace("-", "").isdigit() else 0)):
            if ldata == "none" or not isinstance(ldata, dict):
                continue
            try:
                lid = int(sid)
            except (ValueError, TypeError):
                continue
            w = _DictWrapper(ldata, id_=lid)
            w.location_id = lid
            if isinstance(comp_locs, list) and 0 <= lid - 1 < len(comp_locs):
                w.slug = str(comp_locs[lid - 1])
            elif isinstance(comp_locs, dict):
                w.slug = str(comp_locs.get(str(lid), comp_locs.get(lid, sid)))
            else:
                w.slug = str(sid)
            w.name = ldata.get("name") or w.slug
            pop_data = ldata.get("population")
            if isinstance(pop_data, dict):
                pops = pop_data.get("pops")
                w.population = sum(_float(x, 0.0) for x in (pops if isinstance(pops, (list, tuple)) else []))
            else:
                w.population = _float(ldata.get("population"), 0.0)
            w.development = _float(ldata.get("development"), 0.0)
            w.control = _float(ldata.get("control"), 0.0)
            w.income = _float(ldata.get("income"), 0.0) or _float(ldata.get("tax"), 0.0)
            w.tax_base = _float(ldata.get("tax_base"), 0.0) or _float(ldata.get("tax"), 0.0)
            w.rank = str(ldata.get("rank", ""))
            w.is_coastal = ldata.get("is_coastal") == "yes"
            w.is_capital = ldata.get("is_capital") == "yes"
            w.vegetation = ldata.get("vegetation")
            owner_id = ldata.get("owner")
            w.owner = self._countries.get(int(owner_id)) if owner_id is not None else None
            market_id = ldata.get("market")
            market_name = None
            if market_id is not None:
                mm = mm_db.get(str(int(market_id)))
                center = mm.get("center") if isinstance(mm, dict) else None
                if center is not None:
                    center_id = int(center)
                    cen = result.get(center_id)
                    if cen is not None:
                        market_name = cen.slug
                    elif isinstance(comp_locs, list) and 0 <= center_id - 1 < len(comp_locs):
                        market_name = str(comp_locs[center_id - 1])
                if market_name is None:
                    market_name = str(market_id)
            w.market = SimpleNamespace(name=market_name) if market_name is not None else None
            prov_id = ldata.get("province")
            province_slug = None
            if prov_id is not None:
                prov = prov_db.get(str(int(prov_id)))
                if isinstance(prov, dict):
                    province_slug = prov.get("province_definition")
            w.province = SimpleNamespace(slug=province_slug) if province_slug else None
            result[lid] = w
        return result

    def _build_buildings(self) -> dict:
        result = {}
        bm = self._data.get("building_manager") or {}
        db = bm.get("database") if isinstance(bm, dict) else {}
        if not isinstance(db, dict):
            return result
        for bid, bdata in db.items():
            if bdata == "none" or not isinstance(bdata, dict):
                continue
            try:
                building_id = int(bid)
            except (ValueError, TypeError):
                continue
            w = _DictWrapper(bdata, id_=building_id)
            loc_id = bdata.get("location")
            w.location = self._locations.get(int(loc_id)) if loc_id is not None else None
            w.name = bdata.get("name") or bdata.get("building") or str(building_id)
            w.slug = str(bdata.get("building", building_id))
            w.level = int(bdata.get("level", 0))
            w.max_level = int(bdata.get("max_level", 0))
            w.employment = _float(bdata.get("employment"), 0.0)
            w.pop_type = str(bdata.get("pop_type", ""))
            result[building_id] = w
        return result

    @property
    def countries(self) -> dict:
        return self._countries

    @property
    def locations(self) -> dict:
        return self._locations

    @property
    def buildings(self) -> dict:
        return self._buildings


def _float(v, default=0.0):
    if v is None:
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def get_latest_save_path(save_games_dir: str) -> str | None:
    """Find the most recent .eu5 file in the given directory by modification time.

    Args:
        save_games_dir: Path to the save games folder.

    Returns:
        Full path to the latest save file, or None if no .eu5 files exist.
    """
    path = Path(save_games_dir)
    if not path.is_dir():
        return None
    saves = list(path.glob("*.eu5"))
    if not saves:
        return None
    latest = max(saves, key=lambda p: p.stat().st_mtime)
    return str(latest.resolve())


def load_save(path: str | None = None):
    """Load an EU5 save game.

    Tries pyeu5 (Rakaly) first. For text-format saves when Rakaly fails,
    falls back to native parsing.

    Args:
        path: Explicit path to a save file. If None, uses the latest save from
            save_games_dir in config, or falls back to pyeu5's Save.latest().

    Returns:
        Save object (eu5.Save or SaveAdapter) with .locations, .countries, .buildings, .name, .game_date.

    Raises:
        FileNotFoundError: If no save file is found.
        RuntimeError: If save cannot be parsed (with guidance to use debug mode).
    """
    from eu5 import Save

    def _load(path_str: str):
        try:
            return Save(path_str)
        except subprocess.CalledProcessError as e:
            if _is_text_format_save(path_str):
                data = _parse_text_save(path_str)
                return SaveAdapter(data)
            stderr = (e.stderr or b"").decode(errors="replace")
            raise RuntimeError(
                "Rakaly could not parse this save. Use debug mode (-debug_mode launch option) "
                "to create text-format saves, or use a non-Ironman save. "
                f"Rakaly error: {stderr[:200]}"
            ) from e

    if path is not None:
        return _load(path)
    config = load_config()
    save_dir = config.get("save_games_dir")
    if not save_dir:
        from platformdirs import user_documents_dir
        save_dir = str(Path(user_documents_dir()) / "Paradox Interactive" / "Europa Universalis V" / "save games")
    latest = get_latest_save_path(save_dir)
    if not latest:
        raise FileNotFoundError(f"No .eu5 save files found in {save_dir}")
    return _load(latest)


def inspect_savegame(save, max_depth: int = 5, max_items: int = 8) -> str:
    """Show all top-level attributes of a save and their structure.

    Works with pyeu5 Save and SaveAdapter. Returns a human-readable tree of keys,
    types, and sample values. Useful for understanding the raw save structure.

    Args:
        save: Loaded save (eu5.Save or SaveAdapter).
        max_depth: How deep to recurse into nested dicts.
        max_items: Max list/dict items to show before truncating with "...".

    Returns:
        Multiline string with the structure.
    """
    data = getattr(save, "_data", None)
    if data is None or not isinstance(data, dict):
        return "No _data dict on this save object."

    def _tree(val, depth: int, path: str) -> list[str]:
        indent = "  " * depth
        if depth >= max_depth:
            return [f"{indent}{path} -> ..."]
        if val is None:
            return [f"{indent}{path} = None"]
        if isinstance(val, bool):
            return [f"{indent}{path} = {'yes' if val else 'no'}"]
        if isinstance(val, (int, float)):
            return [f"{indent}{path} = {val}"]
        if isinstance(val, str):
            s = repr(val)[:70] + ("..." if len(repr(val)) > 70 else "")
            return [f"{indent}{path} = {s}"]
        if isinstance(val, dict):
            keys = sorted(val.keys(), key=lambda k: (str(k).isdigit(), str(k)))
            if not keys:
                return [f"{indent}{path} = {{}}"]
            result = [f"{indent}{path} = dict ({len(keys)} keys)"]
            for k in keys[:max_items]:
                result.extend(_tree(val[k], depth + 1, k))
            if len(keys) > max_items:
                result.append(f"{indent}  ... (+{len(keys) - max_items} more)")
            return result
        if isinstance(val, (list, tuple)):
            n = len(val)
            result = [f"{indent}{path} = list ({n} items)"]
            for i in range(min(n, max_items)):
                result.extend(_tree(val[i], depth + 1, f"[{i}]"))
            if n > max_items:
                result.append(f"{indent}  ... (+{n - max_items} more)")
            return result
        return [f"{indent}{path} = {type(val).__name__}"]

    lines = ["# Savegame structure (all top-level keys)\n"]
    for k in sorted(data.keys(), key=lambda x: (str(x).isdigit(), str(x))):
        lines.extend(_tree(data[k], 0, str(k)))
    return "\n".join(lines)


def _flatten_dict(d: dict, prefix: str = "") -> dict:
    """Recursively flatten nested dict to single-level with underscore keys. Keeps scalars as-is."""
    out = {}
    for k, v in d.items():
        key = f"{prefix}_{k}" if prefix else str(k)
        if isinstance(v, dict):
            out.update(_flatten_dict(v, key))
        elif isinstance(v, (list, tuple)):
            out[key] = v
        else:
            out[key] = v
    return out


def _safe_get(obj, attr: str, default=None):
    """Safely get an attribute, returning default on AttributeError or None."""
    try:
        val = getattr(obj, attr, default)
        return val if val is not None else default
    except (AttributeError, TypeError):
        return default


# Column names for get_locations_df (explicit, no string iteration)
_LOCATIONS_RENAME = {
    "estate_tax_nobles_estate": "nobles_tax",
    "estate_tax_clergy_estate": "clergy_tax",
    "estate_tax_burghers_estate": "burghers_tax",
    "estate_tax_peasants_estate": "peasants_tax",
    "institutions_feudalism": "feudalism",
    "institutions_legalism": "legalism",
    "institutions_professional_armies": "professional_armies",
    "population_pop_stats_nobles_population_ratio": "nobles",
    "population_pop_stats_nobles_unemployed": "nobles_u",
    "population_pop_stats_clergy_population_ratio": "clergy",
    "population_pop_stats_clergy_unemployed": "clergy_u",
    "population_pop_stats_burghers_population_ratio": "burghers",
    "population_pop_stats_burghers_unemployed": "burghers_u",
    "population_pop_stats_soldiers_population_ratio": "soldiers",
    "population_pop_stats_soldiers_unemployed": "soldiers_u",
    "population_pop_stats_laborers_population_ratio": "laborers",
    "population_pop_stats_laborers_unemployed": "laborers_u",
    "population_pop_stats_labourers_population_ratio": "laborers",
    "population_pop_stats_labourers_unemployed": "laborers_u",
    "population_pop_stats_peasants_population_ratio": "peasants",
    "population_pop_stats_peasants_unemployed": "peasants_u",
    "population_pop_stats_tribesmen_population_ratio": "tribesmen",
    "population_pop_stats_tribesmen_unemployed": "tribesmen_u",
    "population_pop_stats_slaves_population_ratio": "slaves",
    "population_pop_stats_slaves_unemployed": "slaves_u",
}
_LOCATIONS_KEEP = (
    "location_id", "name", "slug", "owner", "controller", "previous_owner",
    "market", "second_best_market", "market_access", "market_attraction",
    "second_best_market_access", "cores", "religion", "culture", "secondary_culture",
    "cultural_unity", "language", "dialect", "last_owner_change", "last_controller_change",
    "rank", "raw_material", "max_raw_material_workers", "prosperity", "development",
    "control", "road_to_capital", "proximity", "local_proximity_propagation", "value_flow",
    "province", "winter", "tax", "possible_tax", "population", "owner_name",
    "market_name", "province_slug",
    "estate_tax_nobles_estate", "estate_tax_clergy_estate", "estate_tax_burghers_estate",
    "estate_tax_peasants_estate", "institutions_feudalism", "institutions_legalism",
    "institutions_professional_armies",
    "population_pop_stats_nobles_population_ratio", "population_pop_stats_nobles_unemployed",
    "population_pop_stats_clergy_population_ratio", "population_pop_stats_clergy_unemployed",
    "population_pop_stats_burghers_population_ratio", "population_pop_stats_burghers_unemployed",
    "population_pop_stats_soldiers_population_ratio", "population_pop_stats_soldiers_unemployed",
    "population_pop_stats_laborers_population_ratio", "population_pop_stats_laborers_unemployed",
    "population_pop_stats_labourers_population_ratio", "population_pop_stats_labourers_unemployed",
    "population_pop_stats_peasants_population_ratio", "population_pop_stats_peasants_unemployed",
    "population_pop_stats_tribesmen_population_ratio", "population_pop_stats_tribesmen_unemployed",
    "population_pop_stats_slaves_population_ratio", "population_pop_stats_slaves_unemployed",
)
_LOCATIONS_ORDER = (
    "location_id", "slug", "rank", "development", "total_population", "tax", "possible_tax",
    "nobles", "nobles_u", "clergy", "clergy_u", "burghers", "burghers_u",
    "soldiers", "soldiers_u", "laborers", "laborers_u", "peasants", "peasants_u",
    "tribesmen", "tribesmen_u", "slaves", "slaves_u",
)


def get_locations_df(save) -> pd.DataFrame:
    """Extract locations from a save into a DataFrame with short column names.

    Flattens nested location data, keeps base columns, renames for brevity.
    total_population: sum of each pop's size from population.database, * 1000 (matches pyeu5).
    nobles/clergy/etc are ratios, not counts.
    """
    data = getattr(save, "_data", None)
    if not data or not isinstance(data, dict):
        return pd.DataFrame()
    locs = (data.get("locations") or {}).get("locations") or {}
    if not isinstance(locs, dict):
        return pd.DataFrame()

    meta = data.get("metadata") or (next(iter(data.values()), {}) or {}).get("metadata") or {}
    compat = meta.get("compatibility") or {}
    comp_locs = compat.get("locations") or []
    mm_db = (data.get("market_manager") or {}).get("database") or {}
    prov_db = (data.get("provinces") or {}).get("database") or {}
    countries_db = (data.get("countries") or {}).get("database") or {}
    pop_db = (data.get("population") or {}).get("database") or {}

    rows = []
    for loc_id_str, loc_data in locs.items():
        if loc_data == "none" or not isinstance(loc_data, dict):
            continue
        try:
            loc_id = int(loc_id_str)
        except (ValueError, TypeError):
            continue
        flat = _flatten_dict(loc_data)
        flat["location_id"] = loc_id
        if isinstance(comp_locs, list) and 0 <= loc_id - 1 < len(comp_locs):
            flat["slug"] = comp_locs[loc_id - 1]
        owner_id = loc_data.get("owner")
        if owner_id is not None:
            c = countries_db.get(str(int(owner_id))) if isinstance(countries_db, dict) else None
            flat["owner_name"] = (c.get("country_name") or c.get("definition") or c.get("name")) if isinstance(c, dict) else None
        market_id = loc_data.get("market")
        if market_id is not None and isinstance(mm_db, dict):
            mm = mm_db.get(str(int(market_id)))
            if isinstance(mm, dict) and (center := mm.get("center")) is not None and isinstance(comp_locs, list):
                cid = int(center)
                flat["market_name"] = comp_locs[cid - 1] if 0 <= cid - 1 < len(comp_locs) else str(market_id)
        prov_id = loc_data.get("province")
        if prov_id is not None and isinstance(prov_db, dict):
            prov = prov_db.get(str(int(prov_id)))
            if isinstance(prov, dict):
                flat["province_slug"] = prov.get("province_definition")
        pop_data = loc_data.get("population")
        if isinstance(pop_data, dict):
            pops = pop_data.get("pops")
            if isinstance(pops, (list, tuple)):
                if isinstance(pop_db, dict) and pop_db:
                    # pyeu5 logic: resolve pop IDs -> pop.size (in thousands), sum, * 1000
                    total = 0.0
                    for pop_id in pops:
                        if pop_id is None:
                            continue
                        rec = pop_db.get(str(int(pop_id)))
                        if isinstance(rec, dict):
                            size = rec.get("size")
                            if size is not None:
                                total += float(size)
                    flat["population"] = total * 1000.0
                else:
                    # minimal fixture: pops are direct population values
                    flat["population"] = sum(float(x) for x in pops if x is not None)
        flat["name"] = flat.get("name") or flat.get("slug", "")
        rows.append(flat)

    df = pd.DataFrame(rows)
    keep_cols = [c for c in _LOCATIONS_KEEP if c in df.columns]
    df = df[keep_cols].rename(columns=_LOCATIONS_RENAME)

    df["total_population"] = df["population"].fillna(0) if "population" in df.columns else 0.0

    order_set = frozenset(_LOCATIONS_ORDER)
    ordered = [c for c in _LOCATIONS_ORDER if c in df.columns]
    other = [c for c in df.columns if c not in order_set]
    return df[ordered + other]


def build_save_comparison_df(
    saves: dict[str, pd.DataFrame],
    group_col: str,
    metric_cols: tuple[str, ...] = ("development", "total_population"),
    aggregation_method: str = "sum",
    sort_by: str | None = None,
    fill_value: float = 0.0,
) -> pd.DataFrame:
    """Merge grouped aggregates from multiple saves into one wide DataFrame.

    Args:
        saves: {label: locations_df}
        group_col: Column to group by (e.g. "religion", "province")
        metric_cols: Columns to aggregate (default development, total_population)
        aggregation_method: How to aggregate within each group ("sum", "mean", "median")
        sort_by: Column to sort by, e.g. "total_population_game_start" (default: first save's population)
        fill_value: Fill missing groups with this value.

    Returns:
        One DataFrame: rows = groups, columns = {metric}_{label} for each save.
    """
    merged = None
    first_label = None

    for label, df in saves.items():
        if first_label is None:
            first_label = label
        cols = [c for c in metric_cols if c in df.columns]
        if not cols or group_col not in df.columns:
            continue
        grouped = df.groupby(group_col, dropna=False)[cols]
        agg_fn = getattr(grouped, aggregation_method, None)
        if agg_fn is None:
            raise ValueError(
                f"aggregation_method must be sum, mean, median, min, or max; got {aggregation_method!r}"
            )
        result = agg_fn().rename(columns={c: f"{c}_{label}" for c in cols})
        if merged is None:
            merged = result
        else:
            merged = merged.join(result, how="outer")

    if merged is None:
        return pd.DataFrame()

    merged = merged.fillna(fill_value).round(0)
    merged = merged.reset_index()

    if sort_by and sort_by in merged.columns:
        merged = merged.sort_values(sort_by, ascending=False).reset_index(drop=True)
    elif first_label and f"total_population_{first_label}" in merged.columns:
        merged = merged.sort_values(
            f"total_population_{first_label}", ascending=False
        ).reset_index(drop=True)

    return merged


def get_countries_df(save) -> pd.DataFrame:
    """Extract countries from a save into a pandas DataFrame."""
    rows = []
    for country_id, country in save.countries.items():
        rows.append({
            "country_id": country_id,
            "name": _safe_get(country, "name", ""),
            "population": _safe_get(country, "population", 0.0),
            "gold": _safe_get(country, "gold", 0.0),
            "stability": _safe_get(country, "stability", 0.0),
            "prestige": _safe_get(country, "prestige", 0.0),
            "monthly_income": _safe_get(country, "monthly_income", 0.0),
            "government_type": _safe_get(country, "government_type", ""),
        })
    return pd.DataFrame(rows)


def get_buildings_df(save) -> pd.DataFrame:
    """Extract buildings from a save into a pandas DataFrame (flattened with location/country)."""
    rows = []
    for building_id, building in save.buildings.items():
        location = _safe_get(building, "location")
        loc_id = _safe_get(location, "location_id") if location else None
        if loc_id is None and location is not None:
            # Fallback: look up by matching in save.locations
            for lid, loc in save.locations.items():
                if loc is location:
                    loc_id = lid
                    break
        owner = location.owner if location else None
        rows.append({
            "building_id": building_id,
            "name": _safe_get(building, "name", ""),
            "slug": _safe_get(building, "slug", ""),
            "level": _safe_get(building, "level", 0),
            "max_level": _safe_get(building, "max_level", 0),
            "employment": _safe_get(building, "employment", 0.0),
            "pop_type": _safe_get(building, "pop_type", ""),
            "location_id": loc_id,
            "location_name": location.name if location else None,
            "owner_name": owner.name if owner else None,
        })
    return pd.DataFrame(rows)


def get_religion_data():
    """Return ReligionData for resolving religion IDs to display names. Uses config game_path/mod_path."""
    from core.data.religion_data import ReligionData
    from core.parser.path_resolver import PathResolver

    config = load_config()
    path_resolver = PathResolver(
        config.get("game_path", ""), config.get("mod_path", "")
    )
    return ReligionData(path_resolver)
