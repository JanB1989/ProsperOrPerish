"""Compare the Excel goods modifier matrix with modifiers parsed from game files."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

from analysis.building_levels.building_analysis import get_path, load_goods_output_modifiers
from analysis.building_levels.scripts.generate_goods_modifier_matrix import (
    ATTRIBUTES,
    GOODS,
)

# Map game modifier names in pp_location_modifier_adjustments to matrix attribute names
LOCATION_ATTR_MAP = {
    "coastal": "is_coastal",
    "river_flowing_through": "has_river",
    "adjacent_to_lake": "is_adjacent_to_lake",
}

TOLERANCE = 0.01


def _extract_inner_block(content: str, start: int) -> tuple[str, int] | None:
    """Extract content of first {...} starting at start. Returns (inner_content, end_pos)."""
    if start >= len(content) or content[start] != "{":
        return None
    depth = 0
    i = start
    while i < len(content):
        if content[i] == "{":
            depth += 1
        elif content[i] == "}":
            depth -= 1
            if depth == 0:
                return content[start + 1 : i], i + 1
        i += 1
    return None


def parse_vegetation_file(path: Path) -> dict[str, dict[str, float]]:
    """Parse pp_vegetation_changes.txt TRY_INJECT blocks with location_modifier."""
    content = path.read_text(encoding="utf-8")
    result: dict[str, dict[str, float]] = {}
    mod_line_re = re.compile(
        r"local_(fruit|fish|wool|livestock|millet|wheat|maize|rice|legumes|potato|olives|leather|wild_game|fur)_output_modifier\s*=\s*([\d.-]+)"
    )

    pattern = re.compile(
        r"TRY_INJECT:(\w+)\s*=\s*\{\s*location_modifier\s*=\s*\{",
        re.DOTALL,
    )
    for m in pattern.finditer(content):
        attr = m.group(1)
        matched = m.group(0)
        first_brace = matched.index("{")
        second_brace = matched.index("{", first_brace + 1)
        inner = _extract_inner_block(content, m.start() + second_brace)
        if inner is None:
            continue
        inner_content, _ = inner
        mods: dict[str, float] = {}
        for line in inner_content.split("\n"):
            mm = mod_line_re.search(line)
            if mm:
                good, val_str = mm.group(1), mm.group(2)
                mods[good] = float(val_str)
        if mods:
            result[attr] = mods

    return result


def parse_topography_file(path: Path) -> dict[str, dict[str, float]]:
    """Parse pp_topography_changes.txt - same structure as vegetation."""
    return parse_vegetation_file(path)


def parse_climate_file(path: Path) -> dict[str, dict[str, float]]:
    """Parse pp_climate_changes.txt - same structure as vegetation."""
    return parse_vegetation_file(path)


def parse_location_modifier_adjustments(path: Path) -> dict[str, dict[str, float]]:
    """Parse coastal, river_flowing_through, adjacent_to_lake from pp_location_modifier_adjustments.txt."""
    content = path.read_text(encoding="utf-8")
    result: dict[str, dict[str, float]] = {}
    mod_line_re = re.compile(
        r"local_(fruit|fish|wool|livestock|millet|wheat|maize|rice|legumes|potato|olives|leather|wild_game|fur)_output_modifier\s*=\s*([\d.-]+)"
    )

    for game_key, matrix_attr in LOCATION_ATTR_MAP.items():
        patterns = [
            rf"TRY_REPLACE:{re.escape(game_key)}\s*=\s*\{{",
            rf"TRY_INJECT:{re.escape(game_key)}\s*=\s*\{{",
            rf"{re.escape(game_key)}\s*=\s*\{{",
        ]
        for pat in patterns:
            m = re.search(pat, content)
            if m:
                block = _extract_inner_block(content, m.end() - 1)
                if block is None:
                    break
                inner_content, _ = block
                mods: dict[str, float] = {}
                for line in inner_content.split("\n"):
                    mm = mod_line_re.search(line)
                    if mm:
                        good, val_str = mm.group(1), mm.group(2)
                        mods[good] = float(val_str)
                if mods:
                    result[matrix_attr] = mods
                break

    return result


def parse_all_mod_files(mod_path: Path) -> dict[str, dict[str, float]]:
    """Parse all modifier files and merge into attr -> {good -> value}."""
    combined: dict[str, dict[str, float]] = {}

    def merge(parsed: dict[str, dict[str, float]]) -> None:
        for attr, mods in parsed.items():
            combined[attr] = mods

    merge(
        parse_vegetation_file(
            mod_path / "in_game" / "common" / "vegetation" / "pp_vegetation_changes.txt"
        )
    )
    merge(
        parse_topography_file(
            mod_path / "in_game" / "common" / "topography" / "pp_topography_changes.txt"
        )
    )
    merge(
        parse_climate_file(
            mod_path / "in_game" / "common" / "climates" / "pp_climate_changes.txt"
        )
    )
    merge(
        parse_location_modifier_adjustments(
            mod_path
            / "main_menu"
            / "common"
            / "static_modifiers"
            / "pp_location_modifier_adjustments.txt"
        )
    )

    return combined


def test_matrix_vs_game_files():
    """Excel matrix must match modifiers parsed from game files."""
    try:
        df = load_goods_output_modifiers(validate=False)
    except FileNotFoundError:
        pytest.skip("goods_output_modifiers.xlsx not found (run generate_goods_modifier_matrix.py)")

    mod_path = Path(get_path("mod_path"))
    if not mod_path.exists():
        pytest.skip(f"Mod path not found: {mod_path}")

    parsed = parse_all_mod_files(mod_path)

    # Build Excel matrix as attr -> good -> value (treat NaN/absent as 0)
    excel_matrix: dict[str, dict[str, float]] = {}
    for attr in df.columns:
        excel_matrix[attr] = {}
        for good in df.index:
            val = df.loc[good, attr]
            v = 0.0 if pd.isna(val) else float(val)
            if abs(v) >= TOLERANCE:
                excel_matrix[attr][good] = v

    errors: list[str] = []

    # 1. Attributes in Excel but missing in files
    for attr in ATTRIBUTES:
        if attr not in parsed and (attr in excel_matrix and excel_matrix[attr]):
            errors.append(f"Attribute {attr}: in Excel with non-zero values but missing in game files")

    # 2. Value mismatches (for attributes present in both)
    for attr in ATTRIBUTES:
        excel_vals = excel_matrix.get(attr, {})
        parsed_vals = parsed.get(attr, {})

        for good in GOODS:
            e_val = excel_vals.get(good, 0.0)
            p_val = parsed_vals.get(good, 0.0)
            if abs(e_val - p_val) > TOLERANCE:
                errors.append(f"{attr} / {good}: Excel={e_val}, file={p_val}")

    assert not errors, "\n".join(errors)
