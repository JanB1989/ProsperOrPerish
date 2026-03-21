"""Tests for the savegame loader module."""

import os
import subprocess
import time

import pandas as pd
import pytest

from analysis.building_levels.building_analysis.utils import load_config
from analysis.savegame.datalocations import create_datalocations_pkl_from_save
from analysis.savegame.loader import (
    buildings_df_from_pkl,
    get_buildings_df,
    get_cookery_buildings_df,
    get_countries_df,
    get_latest_save_path,
    get_locations_df,
    get_market_goods_df,
    inspect_savegame,
    load_save,
    locations_df_from_pkl,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
MINIMAL_TEXT_SAVE = os.path.join(FIXTURES_DIR, "minimal_text_save.eu5")


def _has_save_files():
    """True if save_games_dir exists and contains .eu5 files."""
    try:
        cfg = load_config()
        d = cfg.get("save_games_dir", "")
        return d and os.path.isdir(d) and bool(get_latest_save_path(d))
    except Exception:
        return False


def test_get_latest_save_path_returns_none_when_empty_dir(tmp_path):
    """Empty directory returns None."""
    assert get_latest_save_path(str(tmp_path)) is None


def test_get_latest_save_path_returns_none_when_no_eu5_files(tmp_path):
    """Directory with non-.eu5 files returns None."""
    (tmp_path / "other.txt").write_text("x")
    (tmp_path / "save.eu4").touch()
    assert get_latest_save_path(str(tmp_path)) is None


def test_get_latest_save_path_returns_most_recent(tmp_path):
    """Returns the most recently modified .eu5 file."""
    older = tmp_path / "older.eu5"
    newer = tmp_path / "newer.eu5"
    older.write_bytes(b"SAV02003fb9bd370004e75d00000000\n")
    newer.write_bytes(b"SAV02003fb9bd370004e75d00000000\n")
    older.touch()
    time.sleep(0.11)  # Ensure newer has later mtime (some FS have ~100ms resolution)
    newer.touch()
    result = get_latest_save_path(str(tmp_path))
    assert result is not None
    assert "newer.eu5" in result


def test_get_latest_save_path_returns_only_path_when_single_file(tmp_path):
    """Single .eu5 file is returned."""
    save_file = tmp_path / "autosave.eu5"
    save_file.write_bytes(b"SAV02003fb9bd370004e75d00000000\n")
    result = get_latest_save_path(str(tmp_path))
    assert result == str(save_file.resolve())


def test_get_latest_save_path_returns_none_for_nonexistent_dir():
    """Nonexistent directory returns None."""
    assert get_latest_save_path("/nonexistent/path/12345") is None


def test_inspect_savegame_shows_structure():
    """inspect_savegame returns a string describing save structure."""
    save = load_save(path=MINIMAL_TEXT_SAVE)
    result = inspect_savegame(save, max_depth=3, max_items=5)
    assert "locations" in result or "Locations" in result
    assert isinstance(result, str)
    assert len(result) > 50


def test_load_save_text_format():
    """load_save loads text-format fixture and get_*_df return expected data."""
    save = load_save(path=MINIMAL_TEXT_SAVE)
    assert save is not None
    assert hasattr(save, "locations")
    assert hasattr(save, "countries")
    assert hasattr(save, "buildings")
    assert hasattr(save, "name")
    assert save.name == "Minimal Test"
    assert len(save.locations) == 2
    assert len(save.countries) == 1
    df = get_locations_df(save)
    assert len(df) == 2
    assert "name" in df.columns
    assert "population" in df.columns
    assert "location_id" in df.columns
    assert "stockholm" in df["name"].values
    assert "norrtalje" in df["name"].values


def test_get_locations_df_resolves_owner_market_province():
    """owner_name is country tag/name not id; market_name is center location slug; province_slug resolved."""
    save = load_save(path=MINIMAL_TEXT_SAVE)
    df = get_locations_df(save)
    # owner_name should be SWE (country tag), not "1"
    assert (df["owner_name"] == "SWE").all()
    assert (df["country_tag"] == "SWE").all()
    assert (df["owner_country_id"] == 1).all()
    # market_name should be stockholm (center of market 1 is location 1), not "1"
    assert (df["market_name"] == "stockholm").all()
    # province_slug should be uppland_province, not None
    assert (df["province_slug"] == "uppland_province").all()


def test_get_locations_df_population_from_pops():
    """population is sum of pops when location has nested population.pops."""
    save = load_save(path=MINIMAL_TEXT_SAVE)
    df = get_locations_df(save)
    # Stockholm (loc 1): 50+25+10+5+3+2+1+1+1 = 98
    row1 = df[df["location_id"] == 1].iloc[0]
    assert row1["population"] == 98.0
    # Norrtalje (loc 2): 25+15+5+2+1+1+0+0+0 = 49
    row2 = df[df["location_id"] == 2].iloc[0]
    assert row2["population"] == 49.0


def test_get_countries_df_uses_country_name_or_definition():
    """Country name comes from country_name or definition, not raw id."""
    save = load_save(path=MINIMAL_TEXT_SAVE)
    df = get_countries_df(save)
    assert (df["name"] == "SWE").all()
    assert (df["country_tag"] == "SWE").all()


def test_get_buildings_df_minimal_includes_production_methods():
    """Text fixture: cookery building has active production method ids."""
    save = load_save(path=MINIMAL_TEXT_SAVE)
    df = get_buildings_df(save)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["slug"] == "cookery"
    assert row["location_id"] == 1
    assert "production_method_ids" in df.columns
    assert "production_methods" in df.columns
    assert set(row["production_method_ids"]) == {"pp_cookery_khichdi", "pp_cookery_beer"}
    assert row["production_methods"] == "pp_cookery_beer|pp_cookery_khichdi"


def test_get_cookery_buildings_df_minimal():
    """get_cookery_buildings_df filters to cookery only."""
    save = load_save(path=MINIMAL_TEXT_SAVE)
    df = get_cookery_buildings_df(save)
    assert len(df) == 1
    assert df.iloc[0]["slug"] == "cookery"


def test_get_market_goods_df_minimal_fixture():
    """All goods rows flattened: nested supplied/demand become supplied_* keys."""
    save = load_save(path=MINIMAL_TEXT_SAVE)
    mg = get_market_goods_df(save)
    assert len(mg) == 1
    row = mg.iloc[0]
    assert row["market_id"] == 1
    assert row["market_center_slug"] == "stockholm"
    assert row["good_id"] == "iron"
    assert row["price"] == 3.5
    assert row["supply"] == 100.0
    assert row["demand"] == 50.0
    assert row["supplied_Building"] == 10.0
    assert row["supplied_Pops"] == 5.0
    assert row["demanded_Building"] == 2.0


@pytest.mark.slow
@pytest.mark.skipif(not _has_save_files(), reason="No save files available")
def test_get_market_goods_df_real_save_has_rows_and_columns():
    """Packed save: eu5 markets path yields one row per good with flattened fields."""
    config = load_config()
    save_dir = config.get("save_games_dir")
    latest = get_latest_save_path(save_dir or "")
    if not latest:
        pytest.skip("No save files in directory")
    try:
        save = load_save(path=latest)
    except subprocess.CalledProcessError as e:
        pytest.skip(f"pyeu5/Rakaly could not parse save: {e}")
    mg = get_market_goods_df(save)
    assert len(mg) >= 1, "expected at least one market good row"
    assert "market_id" in mg.columns and "good_id" in mg.columns
    assert "market_center_slug" in mg.columns
    # Spot-check: common EU5 good keys appear on at least one row when present in save
    sample_cols = {"price", "supply", "demand"}
    assert sample_cols.intersection(set(mg.columns)), f"expected some of {sample_cols} in {list(mg.columns)[:20]}"


def test_load_save_raises_clear_error_for_binary(tmp_path):
    """When given a binary/packed save that Rakaly rejects, load_save raises with guidance."""
    binary_save = tmp_path / "binary.eu5"
    # Header looks like text save, but body is binary - _is_text_format_save returns False
    binary_save.write_bytes(b"SAV02001e1576a50004dbc200000000\n\x00\x01\x02\x03\x04\x05")
    with pytest.raises(RuntimeError) as exc_info:
        load_save(path=str(binary_save))
    msg = str(exc_info.value)
    assert "Rakaly" in msg
    assert "debug" in msg.lower()


@pytest.mark.slow
@pytest.mark.skipif(not _has_save_files(), reason="No save files available")
def test_load_save_with_explicit_path():
    """load_save accepts an explicit path when a save exists."""
    config = load_config()
    save_dir = config.get("save_games_dir")
    if not save_dir:
        pytest.skip("No save_games_dir in config")
    latest = get_latest_save_path(save_dir)
    if not latest:
        pytest.skip("No save files in directory")
    try:
        save = load_save(path=latest)
    except subprocess.CalledProcessError as e:
        pytest.skip(f"pyeu5/Rakaly could not parse save (e.g. Ironman, invalid header): {e}")
    assert save is not None
    assert hasattr(save, "locations")


@pytest.mark.slow
@pytest.mark.skipif(not _has_save_files(), reason="No save files available")
def test_get_locations_df_returns_dataframe():
    """get_locations_df returns a DataFrame with expected columns."""
    config = load_config()
    save_dir = config.get("save_games_dir")
    latest = get_latest_save_path(save_dir or "")
    if not latest:
        pytest.skip("No save files in directory")
    try:
        save = load_save(path=latest)
    except subprocess.CalledProcessError as e:
        pytest.skip(f"pyeu5/Rakaly could not parse save: {e}")
    df = get_locations_df(save)
    assert hasattr(df, "columns")
    assert "name" in df.columns or len(df) == 0
    assert "population" in df.columns or len(df) == 0


@pytest.mark.slow
@pytest.mark.skipif(not _has_save_files(), reason="No save files available")
def test_get_countries_df_returns_dataframe():
    """get_countries_df returns a DataFrame with expected columns."""
    config = load_config()
    save_dir = config.get("save_games_dir")
    latest = get_latest_save_path(save_dir or "")
    if not latest:
        pytest.skip("No save files in directory")
    try:
        save = load_save(path=latest)
    except subprocess.CalledProcessError as e:
        pytest.skip(f"pyeu5/Rakaly could not parse save: {e}")
    df = get_countries_df(save)
    assert "name" in df.columns or len(df) == 0


@pytest.mark.slow
@pytest.mark.skipif(not _has_save_files(), reason="No save files available")
def test_get_buildings_df_returns_dataframe():
    """get_buildings_df returns a DataFrame with expected columns."""
    config = load_config()
    save_dir = config.get("save_games_dir")
    latest = get_latest_save_path(save_dir or "")
    if not latest:
        pytest.skip("No save files in directory")
    try:
        save = load_save(path=latest)
    except subprocess.CalledProcessError as e:
        pytest.skip(f"pyeu5/Rakaly could not parse save: {e}")
    df = get_buildings_df(save)
    assert "level" in df.columns or len(df) == 0
    assert "location_name" in df.columns or len(df) == 0
    assert "production_method_ids" in df.columns
    assert "production_methods" in df.columns
    if "slug" in df.columns and len(df) > 0:
        cookery = df[df["slug"] == "cookery"]
        if len(cookery) > 0:
            assert any(len(row["production_method_ids"]) > 0 for _, row in cookery.iterrows())


@pytest.mark.slow
@pytest.mark.skipif(not _has_save_files(), reason="No save files available")
def test_get_cookery_buildings_df_real_save():
    """Packed save: cookery rows include production_methods when cookery exists."""
    config = load_config()
    save_dir = config.get("save_games_dir")
    latest = get_latest_save_path(save_dir or "")
    if not latest:
        pytest.skip("No save files in directory")
    try:
        save = load_save(path=latest)
    except subprocess.CalledProcessError as e:
        pytest.skip(f"pyeu5/Rakaly could not parse save: {e}")
    df = get_cookery_buildings_df(save)
    if df.empty:
        pytest.skip("No cookery buildings in this save")
    assert (df["production_methods"].str.len() > 0).any()


def test_create_datalocations_pkl_format_2_payload(tmp_path):
    """Written .pkl is a dict with locations, buildings, market_goods, countries (minimal fixture)."""
    save = load_save(path=MINIMAL_TEXT_SAVE)
    out = tmp_path / "snap.pkl"
    payload = create_datalocations_pkl_from_save(save, out)
    assert payload["format"] == 2
    assert (
        "locations" in payload
        and "buildings" in payload
        and "market_goods" in payload
        and "countries" in payload
    )
    assert isinstance(payload["buildings"], pd.DataFrame)
    assert len(payload["market_goods"]) == 1
    assert len(payload["countries"]) == 1
    rt = pd.read_pickle(out)
    assert rt["format"] == 2
    assert "buildings" in rt and isinstance(rt["buildings"], pd.DataFrame)
    assert buildings_df_from_pkl(rt).equals(rt["buildings"])
    loc = locations_df_from_pkl(rt)
    assert len(loc) == 2
