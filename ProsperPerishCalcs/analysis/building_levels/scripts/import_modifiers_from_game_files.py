"""Parse goods output modifiers from mod game files into the 14×25 matrix shape."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

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


def matrix_from_mod_files(mod_path: Path) -> pd.DataFrame:
    """Build GOODS × ATTRIBUTES DataFrame from parsed game files; missing cells are 0.0."""
    parsed = parse_all_mod_files(mod_path)
    data: dict[str, list[float]] = {}
    for attr in ATTRIBUTES:
        col: list[float] = []
        for good in GOODS:
            v = parsed.get(attr, {}).get(good)
            col.append(0.0 if v is None else float(v))
        data[attr] = col
    return pd.DataFrame(data, index=GOODS)
