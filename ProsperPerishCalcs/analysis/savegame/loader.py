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


def _safe_get(obj, attr: str, default=None):
    """Safely get an attribute, returning default on AttributeError or None."""
    try:
        val = getattr(obj, attr, default)
        return val if val is not None else default
    except (AttributeError, TypeError):
        return default


def get_locations_df(save) -> pd.DataFrame:
    """Extract locations from a save into a pandas DataFrame."""
    rows = []
    for loc_id, loc in save.locations.items():
        owner = _safe_get(loc, "owner")
        market = _safe_get(loc, "market")
        province = _safe_get(loc, "province")
        rows.append({
            "location_id": loc_id,
            "name": _safe_get(loc, "name", ""),
            "slug": _safe_get(loc, "slug", ""),
            "population": _safe_get(loc, "population", 0.0),
            "development": _safe_get(loc, "development", 0.0),
            "control": _safe_get(loc, "control", 0.0),
            "income": _safe_get(loc, "income", 0.0),
            "tax_base": _safe_get(loc, "tax_base", 0.0),
            "rank": _safe_get(loc, "rank", ""),
            "owner_name": owner.name if owner else None,
            "market_name": market.name if market else None,
            "province_slug": province.slug if province else None,
            "is_coastal": _safe_get(loc, "is_coastal", False),
            "is_capital": _safe_get(loc, "is_capital", False),
            "vegetation": _safe_get(loc, "vegetation"),
        })
    return pd.DataFrame(rows)


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
