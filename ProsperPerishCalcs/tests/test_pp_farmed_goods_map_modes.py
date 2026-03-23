"""PP mod: farmed goods in the Cursor rule must have matching local-output map modes.

Set ``PP_MOD_ROOT`` to the ``Prosper or Perish (Population Growth & Food Rework)`` folder
if it is not at the default Documents path. Tests skip when the mod or rule file is missing.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

RULE_FILE = "pp-farmed-goods-output-modifiers.mdc"
MAP_MODES_FILE = Path("in_game/gfx/map/map_modes/pp_local_output_modifier_map_modes.txt")
MAP_MODE_ICON_DIR = Path("main_menu/gfx/interface/icons/map_modes")


def _pp_mod_root() -> Path:
    return Path(
        os.environ.get(
            "PP_MOD_ROOT",
            r"c:\Users\Anwender\Documents\Paradox Interactive\Europa Universalis V\mod"
            r"\Prosper or Perish (Population Growth & Food Rework)",
        )
    )


def _parse_farmed_goods_from_rule(rule_text: str) -> list[str]:
    """Parse the comma-separated goods line after the **Goods** heading."""
    lines = rule_text.splitlines()
    after_goods = False
    for line in lines:
        if line.startswith("**Goods"):
            after_goods = True
            continue
        if not after_goods:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("**"):
            break
        if stripped.startswith("`"):
            continue
        return [p.strip() for p in stripped.split(",") if p.strip()]
    raise ValueError("Could not find farmed goods list in cursor rule")


def _parse_rural_mapmode_goods_from_rule(rule_text: str) -> list[str]:
    """Parse comma-separated goods after **Rural map modes** (PP local-output map modes only)."""
    lines = rule_text.splitlines()
    after = False
    for line in lines:
        if line.startswith("**Rural map modes"):
            after = True
            continue
        if not after:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("**"):
            break
        if stripped.startswith("`"):
            continue
        return [p.strip() for p in stripped.split(",") if p.strip()]
    raise ValueError("Could not find **Rural map modes** list in cursor rule")


def _parse_pp_local_map_mode_goods(mm_text: str) -> list[str]:
    """Goods that have a pp_local_<good>_output_modifier block (file order)."""
    return re.findall(r"^pp_local_(\w+)_output_modifier\s*=", mm_text, re.MULTILINE)


def _parse_geography_indices_per_block(mm_text: str) -> list[tuple[str, int]]:
    """(good, index) for each pp_local_* block that sets category = geography."""
    starts = list(re.finditer(r"^pp_local_(\w+)_output_modifier\s*=", mm_text, re.MULTILINE))
    out: list[tuple[str, int]] = []
    for i, m in enumerate(starts):
        good = m.group(1)
        end = starts[i + 1].start() if i + 1 < len(starts) else len(mm_text)
        block = mm_text[m.start() : end]
        if "category = geography" not in block:
            continue
        im = re.search(r"^\s*index\s*=\s*(\d+)\s*$", block, re.MULTILINE)
        if not im:
            raise ValueError(f"No index= in geography block for {good}")
        out.append((good, int(im.group(1))))
    return out


def _mapmode_legend_key(good: str) -> str:
    return (
        "MAPMODE_PP_LOCAL_"
        + "_".join(p.upper() for p in good.split("_"))
        + "_OUTPUT_MODIFIER"
    )


def _mapmode_picker_name_key(good: str) -> str:
    return f"mapmode_pp_local_{good}_output_modifier_name"


@pytest.fixture(scope="module")
def pp_mod_paths():
    root = _pp_mod_root()
    rule = root / ".cursor" / "rules" / RULE_FILE
    map_modes = root / MAP_MODES_FILE
    if not rule.is_file():
        pytest.skip(f"PP mod or rule missing: {rule}")
    if not map_modes.is_file():
        pytest.skip(f"PP map modes file missing: {map_modes}")
    return root, rule, map_modes


def test_parse_farmed_goods_line_not_empty(pp_mod_paths):
    _, rule_path, _ = pp_mod_paths
    text = rule_path.read_text(encoding="utf-8")
    goods = _parse_farmed_goods_from_rule(text)
    assert len(goods) >= 20
    assert "wheat" in goods
    assert "dyes" not in goods


def test_each_rule_good_has_local_output_map_mode(pp_mod_paths):
    _, rule_path, map_modes_path = pp_mod_paths
    goods = _parse_farmed_goods_from_rule(rule_path.read_text(encoding="utf-8"))
    mm = map_modes_path.read_text(encoding="utf-8")
    missing = []
    for good in goods:
        block = f"pp_local_{good}_output_modifier"
        if not re.search(rf"^{re.escape(block)}\s*=", mm, re.MULTILINE):
            missing.append(block)
    assert not missing, f"Missing map mode block(s): {missing}"


def test_pp_local_map_modes_match_allowed_set(pp_mod_paths):
    """Exactly farmed ∪ rural map-mode goods; no extras (e.g. leather, dyes)."""
    _, rule_path, map_modes_path = pp_mod_paths
    rule_text = rule_path.read_text(encoding="utf-8")
    farmed = set(_parse_farmed_goods_from_rule(rule_text))
    rural = set(_parse_rural_mapmode_goods_from_rule(rule_text))
    allowed = farmed | rural
    mm = map_modes_path.read_text(encoding="utf-8")
    found = set(_parse_pp_local_map_mode_goods(mm))
    assert found == allowed, (
        f"Map mode goods must equal allowed set.\n"
        f"Extra in file: {sorted(found - allowed)}\n"
        f"Missing from file: {sorted(allowed - found)}"
    )


def test_geography_indices_are_vanilla_subgroups(pp_mod_paths):
    """EU5 Geography picker only uses index 0–3 as sub-tabs; 4+ are dropped in-game.

    Vanilla stacks many modes on the same index (e.g. topography, vegetation, climate, winter
    all use 2). PP local-output modes must stay in that range; we standardize on 2.
    """
    _, _, map_modes_path = pp_mod_paths
    pairs = _parse_geography_indices_per_block(map_modes_path.read_text(encoding="utf-8"))
    bad = [(g, i) for g, i in pairs if i not in (0, 1, 2, 3)]
    assert not bad, f"Invalid geography index (must be 0–3): {bad}"
    wrong = [(g, i) for g, i in pairs if i != 2]
    assert not wrong, (
        f"PP local-output geography modes should all use index = 2; got: {wrong}"
    )


def test_each_pp_local_output_map_mode_has_icon(pp_mod_paths):
    """Picker icons: main_menu/gfx/interface/icons/map_modes/<map_mode_id>.dds"""
    root, _, map_modes_path = pp_mod_paths
    icon_dir = root / MAP_MODE_ICON_DIR
    if not icon_dir.is_dir():
        pytest.skip(f"Map mode icon folder missing: {icon_dir}")
    goods = _parse_pp_local_map_mode_goods(map_modes_path.read_text(encoding="utf-8"))
    missing = []
    for g in goods:
        block_id = f"pp_local_{g}_output_modifier"
        if not (icon_dir / f"{block_id}.dds").is_file():
            missing.append(f"{block_id}.dds")
    assert not missing, f"Missing map mode icon file(s) under {icon_dir}: {missing}"


def test_each_allowed_good_has_mapmode_localization(pp_mod_paths):
    _, rule_path, _ = pp_mod_paths
    root = _pp_mod_root()
    loc = root / "main_menu/localization/english/pp_building_adjustments_l_english.yml"
    if not loc.is_file():
        pytest.skip(f"Localization file missing: {loc}")
    rule_text = rule_path.read_text(encoding="utf-8")
    goods = _parse_farmed_goods_from_rule(rule_text) + _parse_rural_mapmode_goods_from_rule(rule_text)
    yml = loc.read_text(encoding="utf-8")
    missing = []
    for g in goods:
        for key in (
            _mapmode_picker_name_key(g),
            _mapmode_legend_key(g),
            _mapmode_legend_key(g) + "_TT_LAND_BREAKDOWN",
        ):
            if key not in yml:
                missing.append(key)
    assert not missing, f"Missing localization key(s): {missing}"
