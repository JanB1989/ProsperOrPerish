"""Ensure Prosper or Perish RGO bonuses cover every vanilla raw_material good."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tools.emit_pp_rgo_modifiers import (
    GAME_GOODS,
    MOD_L10N_EN,
    MOD_OUT,
    PP_GAME_START,
    parse_pp_rgo_bonus_good_ids,
    parse_pp_rgo_goods_from_game_start,
    parse_pp_rgo_loc_good_ids,
    parse_raw_material_goods,
)


def _goods_dir() -> Path:
    env = os.environ.get("EU5_GAME_GOODS_DIR")
    if env:
        return Path(env)
    return GAME_GOODS


def _static_mod_path() -> Path:
    env = os.environ.get("PP_RGO_STATIC_MODIFIERS")
    if env:
        return Path(env)
    return MOD_OUT


def _game_start_path() -> Path:
    env = os.environ.get("PP_GAME_START")
    if env:
        return Path(env)
    return PP_GAME_START


def _rgo_loc_path() -> Path:
    env = os.environ.get("PP_RGO_L10N_EN")
    if env:
        return Path(env)
    return MOD_L10N_EN


@pytest.fixture(scope="module")
def vanilla_raw_materials() -> dict[str, float | None]:
    goods_dir = _goods_dir()
    if not goods_dir.is_dir():
        pytest.skip(f"EU5 goods folder not found: {goods_dir} (set EU5_GAME_GOODS_DIR)")
    return parse_raw_material_goods(goods_dir)


@pytest.fixture(scope="module")
def mod_static_ids() -> set[str]:
    path = _static_mod_path()
    if not path.is_file():
        pytest.skip(f"Mod static modifiers not found: {path} (set PP_RGO_STATIC_MODIFIERS)")
    return parse_pp_rgo_bonus_good_ids(path)


@pytest.fixture(scope="module")
def game_start_ids() -> set[str]:
    path = _game_start_path()
    if not path.is_file():
        pytest.skip(f"pp_game_start.txt not found: {path} (set PP_GAME_START)")
    return parse_pp_rgo_goods_from_game_start(path)


@pytest.fixture(scope="module")
def loc_ids() -> set[str]:
    path = _rgo_loc_path()
    if not path.is_file():
        pytest.skip(f"RGO loc not found: {path} (set PP_RGO_L10N_EN)")
    return parse_pp_rgo_loc_good_ids(path)


def test_vanilla_raw_materials_match_static_modifiers(
    vanilla_raw_materials: dict[str, float | None],
    mod_static_ids: set[str],
) -> None:
    expected = set(vanilla_raw_materials.keys())
    missing = expected - mod_static_ids
    extra = mod_static_ids - expected
    assert not missing, f"pp_rgo_static_bonuses.txt missing goods: {sorted(missing)}"
    assert not extra, f"pp_rgo_static_bonuses.txt has unknown pp_rgo_bonus_* entries: {sorted(extra)}"


def test_vanilla_raw_materials_match_pp_game_start(
    vanilla_raw_materials: dict[str, float | None],
    game_start_ids: set[str],
) -> None:
    expected = set(vanilla_raw_materials.keys())
    missing = expected - game_start_ids
    extra = game_start_ids - expected
    assert not missing, f"pp_game_start missing pp_rgo_bonus for goods: {sorted(missing)}"
    assert not extra, f"pp_game_start references unknown pp_rgo_bonus goods: {sorted(extra)}"


def test_vanilla_raw_materials_match_english_loc(
    vanilla_raw_materials: dict[str, float | None],
    loc_ids: set[str],
) -> None:
    expected = set(vanilla_raw_materials.keys())
    missing = expected - loc_ids
    extra = loc_ids - expected
    assert not missing, f"pp_rgo_modifiers_l_english.yml missing STATIC_MODIFIER_NAME for goods: {sorted(missing)}"
    assert not extra, f"pp_rgo_modifiers_l_english.yml has unknown pp_rgo_bonus entries: {sorted(extra)}"


def test_static_modifiers_and_game_start_agree(
    mod_static_ids: set[str],
    game_start_ids: set[str],
) -> None:
    assert mod_static_ids == game_start_ids, (
        f"Mismatch: static_modifiers only={sorted(mod_static_ids - game_start_ids)} "
        f"game_start only={sorted(game_start_ids - mod_static_ids)}"
    )


def test_pp_game_start_guards_raw_material_link() -> None:
    """Avoids invalid raw_material link on sea / no-RGO locations (see error.log)."""
    path = _game_start_path()
    if not path.is_file():
        pytest.skip(f"pp_game_start.txt not found: {path} (set PP_GAME_START)")
    text = path.read_text(encoding="utf-8")
    assert "limit = { exists = raw_material }" in text, (
        "pp_apply_rgo_static_modifiers must use exists = raw_material before raw_material = goods:* limits"
    )
