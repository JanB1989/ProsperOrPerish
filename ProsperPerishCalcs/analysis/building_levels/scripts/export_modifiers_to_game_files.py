"""Export goods output modifiers from the matrix to mod game files.

Loads goods_output_modifiers.xlsx and syncs modifiers to:
- pp_vegetation_changes.txt (TRY_INJECT)
- pp_topography_changes.txt (TRY_INJECT)
- pp_climate_changes.txt (TRY_INJECT)
- pp_location_modifier_adjustments.txt (coastal, river_flowing_through, adjacent_to_lake)

Skips modifiers with value 0. Run: uv run python -m analysis.building_levels.scripts.export_modifiers_to_game_files
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from analysis.building_levels.building_analysis import get_path, load_goods_output_modifiers

# Matrix goods -> game modifier key (local_{good}_output_modifier)
GOODS = [
    "fruit",
    "fish",
    "wool",
    "livestock",
    "millet",
    "wheat",
    "maize",
    "rice",
    "legumes",
    "potato",
    "olives",
    "leather",
    "wild_game",
    "fur",
]

VEGETATION = ["desert", "sparse", "grasslands", "farmland", "woods", "forest", "jungle"]
TOPOGRAPHY = ["flatland", "hills", "plateau", "mountains", "wetlands", "salt_pans", "atoll"]
CLIMATE = ["tropical", "subtropical", "oceanic", "arid", "cold_arid", "mediterranean", "continental", "arctic"]

def good_to_modifier_key(good: str) -> str:
    return f"local_{good}_output_modifier"


def get_modifiers_for_attribute(df: pd.DataFrame, attr: str) -> dict[str, float]:
    """Return {local_X_output_modifier: value} for non-zero values."""
    result = {}
    if attr not in df.columns:
        return result
    for good in GOODS:
        if good not in df.index:
            continue
        val = df.loc[good, attr]
        if pd.isna(val) or abs(float(val)) < 0.005:
            continue
        result[good_to_modifier_key(good)] = round(float(val), 2)
    return result


def load_matrix():
    """Load matrix from Excel, or fallback to embedded data if Excel unavailable."""
    try:
        return load_goods_output_modifiers(validate=False)
    except Exception as e:
        print(f"Could not load Excel ({e}), using embedded fallback data")
        return _fallback_matrix()


def _clamp_value(v: float, lo: float = -0.35, hi: float = 0.35) -> float:
    """Clamp and round value for fallback matrix."""
    return round(max(lo, min(hi, v)), 2)


def _fallback_matrix() -> pd.DataFrame:
    """Embedded matrix from goods_modifier_matrix notebook output (when Excel unavailable)."""
    data_raw = {
        "flatland": {"wheat": 0.25, "rice": 0.25, "millet": 0.15, "maize": 0.15, "legumes": 0.20},
        "hills": {"wheat": 0.15, "fruit": 0.20, "olives": 0.10, "livestock": 0.08, "wild_game": 0.15, "fur": 0.10},
        "plateau": {"wheat": -0.30, "millet": 0.40, "livestock": 0.20, "wool": 0.10},
        "mountains": {"wheat": -0.20, "rice": -0.30, "maize": -0.20, "potato": 0.20, "livestock": 0.05, "wool": 0.10, "wild_game": 0.10, "fur": 0.10},
        "wetlands": {"rice": 0.20, "fish": 0.15, "wheat": -0.60},
        "salt_pans": {},
        "atoll": {"fish": 0.25},
        "desert": {"fruit": -0.5, "fish": -0.6, "wool": -0.6, "livestock": -0.7, "millet": 0.1, "wheat": -0.7, "maize": -0.5, "rice": -0.8, "legumes": -0.5, "potato": -0.6, "olives": -0.4, "leather": -0.5, "wild_game": -0.7, "fur": -0.7},
        "sparse": {"fruit": -0.20, "fish": -0.20, "wool": 0.10, "livestock": 0.15, "millet": 0.20, "wheat": 0.05, "maize": 0.10, "rice": -0.20, "legumes": 0.05, "potato": 0.10, "olives": 0.10, "leather": 0.10, "wild_game": 0.05, "fur": 0.10},
        "grasslands": {"fruit": 0.10, "wool": 0.25, "livestock": 0.25, "millet": 0.15, "wheat": 0.20, "maize": 0.15, "rice": 0.10, "legumes": 0.15, "potato": 0.15, "olives": 0.15, "leather": 0.20, "wild_game": 0.05},
        "farmland": {"fruit": 0.10, "wool": 0.25, "livestock": 0.25, "millet": 0.15, "wheat": 0.20, "maize": 0.15, "rice": 0.10, "legumes": 0.15, "potato": 0.15, "olives": 0.15, "leather": 0.20, "wild_game": 0.05},
        "woods": {"fruit": 0.05, "wool": 0.25, "livestock": 0.25, "millet": 0.15, "wheat": 0.20, "maize": 0.15, "rice": 0.10, "legumes": 0.15, "potato": 0.15, "olives": 0.15, "leather": 0.20, "wild_game": 0.10, "fur": 0.10},
        "forest": {"fruit": -0.10, "wool": 0.25, "livestock": 0.25, "millet": 0.15, "wheat": -0.10, "maize": 0.15, "rice": 0.10, "legumes": 0.15, "potato": 0.15, "olives": 0.15, "leather": 0.20, "wild_game": 0.20, "fur": 0.20},
        "jungle": {"fruit": 0.10, "wool": 0.25, "livestock": 0.25, "millet": 0.15, "wheat": -0.20, "maize": 0.15, "rice": 0.05, "legumes": 0.15, "potato": 0.15, "olives": 0.15, "leather": 0.20, "wild_game": 0.10, "fur": 0.05},
        "tropical": {"rice": 0.1, "fruit": 0.1, "wheat": -0.15, "potato": -0.1, "maize": 0.05, "wild_game": 0.05, "fur": -0.05},
        "subtropical": {"rice": 0.05, "fruit": 0.05, "olives": 0.05, "wheat": -0.05, "millet": 0.05, "maize": 0.05},
        "oceanic": {"wheat": 0.05, "livestock": 0.05, "fish": 0.05, "legumes": 0.05, "potato": 0.05},
        "arid": {"millet": 0.1, "wheat": -0.1, "rice": -0.15, "livestock": 0.05, "fruit": -0.1},
        "cold_arid": {"millet": 0.05, "wheat": -0.05, "livestock": 0.1, "wool": 0.1, "fur": 0.1, "potato": -0.05},
        "mediterranean": {"wheat": 0.05, "olives": 0.15, "fruit": 0.1, "rice": -0.1, "legumes": 0.05},
        "continental": {"wheat": 0.1, "potato": 0.1, "livestock": 0.05, "millet": 0.05, "legumes": 0.05},
        "arctic": {"wheat": -0.15, "rice": -0.15, "wild_game": 0.15, "fur": 0.15, "fish": 0.1, "wool": 0.1, "fruit": -0.15},
        "has_river": {"fruit": 0.15, "fish": 0.10, "wool": 0.08, "livestock": 0.15, "millet": 0.05, "wheat": 0.20, "maize": 0.15, "rice": 0.25, "legumes": 0.20, "potato": 0.10, "olives": 0.10, "leather": 0.08, "wild_game": 0.05, "fur": 0.05},
        "is_adjacent_to_lake": {"fruit": 0.08, "fish": 0.15, "wool": 0.05, "livestock": 0.10, "wheat": 0.08, "maize": 0.08, "rice": 0.15, "legumes": 0.10, "potato": 0.05, "olives": 0.05, "leather": 0.05, "wild_game": 0.08, "fur": 0.08},
        "is_coastal": {"fruit": 0.05, "fish": 0.25, "rice": 0.05, "olives": 0.08},
    }
    # Clamp all values to [-0.35, 0.35] for consistency with matrix bounds
    data = {
        attr: {g: _clamp_value(vals.get(g, 0)) for g in GOODS}
        for attr, vals in data_raw.items()
    }
    return pd.DataFrame(
        {attr: pd.Series(vals, index=GOODS) for attr, vals in data.items()}
    )


def update_inject_file(
    mod_path: Path,
    rel_path: str,
    attributes: list[str],
    df: pd.DataFrame,
) -> None:
    """Update a TRY_INJECT file (vegetation, topography, climate)."""
    path = mod_path / rel_path
    content = path.read_text(encoding="utf-8")

    for attr in attributes:
        mods = get_modifiers_for_attribute(df, attr)
        if not mods:
            continue

        # Find the TRY_INJECT block for this attribute
        pattern = r"(TRY_INJECT:" + re.escape(attr) + r"\s*=\s*\{\s*location_modifier\s*=\s*\{)(.*?)(\}\s*\})"
        m = re.search(pattern, content, re.DOTALL)
        if not m:
            # Add new block if it doesn't exist
            new_lines = [f"\t\t{k} = {v}" for k, v in sorted(mods.items())]
            new_block = f"TRY_INJECT:{attr} = {{\n\tlocation_modifier = {{\n" + "\n".join(new_lines) + "\n\t}}\n}}\n\n"
            content = content.rstrip() + "\n\n" + new_block
            path.write_text(content, encoding="utf-8")
            print(f"Added {attr} to {rel_path}")
            continue

        prefix, inner, suffix = m.groups()
        # Extract existing lines that are NOT our output modifiers
        existing = []
        output_pattern = re.compile(r"\s*local_(?:fruit|fish|wool|livestock|millet|wheat|maize|rice|legumes|potato|olives|leather|wild_game|fur)_output_modifier\s*=")
        for line in inner.split("\n"):
            if line.strip() and not output_pattern.match(line):
                existing.append(line.rstrip())

        new_inner_lines = existing.copy()
        for k, v in sorted(mods.items()):
            new_inner_lines.append(f"\t\t{k} = {v}")
        new_inner = "\n".join(new_inner_lines)
        new_block = f"{prefix}\n{new_inner}\n\t{suffix}"
        content = content[: m.start()] + new_block + content[m.end() :]

    path.write_text(content, encoding="utf-8")
    print(f"Updated {rel_path}")


def update_location_modifier_adjustments(mod_path: Path, df: pd.DataFrame) -> None:
    """Update coastal, river_flowing_through, and add adjacent_to_lake."""
    path = mod_path / "main_menu" / "common" / "static_modifiers" / "pp_location_modifier_adjustments.txt"
    content = path.read_text(encoding="utf-8")

    # 1. TRY_REPLACE:coastal - add output modifiers from is_coastal
    coastal_mods = get_modifiers_for_attribute(df, "is_coastal")
    if coastal_mods:
        pattern = r"(TRY_REPLACE:coastal\s*=\s*\{\s*game_data\s*=\s*\{[^}]+\}\s*)((?:.*?\n)*?)(\s*\})"
        m = re.search(pattern, content, re.DOTALL)
        if m:
            prefix, inner, suffix = m.group(1, 2, 3)
            # Remove existing local_*_output_modifier from coastal
            inner_cleaned = re.sub(r"\s*local_\w+_output_modifier\s*=\s*[^\n]+\n", "", inner)
            new_lines = [f"\t{k} = {v}" for k, v in sorted(coastal_mods.items())]
            new_inner = inner_cleaned.rstrip() + "\n" + "\n".join(new_lines) + "\n"
            new_block = prefix + new_inner + suffix
            content = content[: m.start()] + new_block + content[m.end() :]
            print("Updated coastal in pp_location_modifier_adjustments.txt")

    # 2. TRY_INJECT:river_flowing_through - add output modifiers from has_river
    river_mods = get_modifiers_for_attribute(df, "has_river")
    if river_mods:
        pattern = r"(TRY_INJECT:river_flowing_through\s*=\s*\{)((?:.*?\n)*?)(\})"
        m = re.search(pattern, content, re.DOTALL)
        if m:
            prefix, inner, suffix = m.group(1, 2, 3)
            inner_cleaned = re.sub(r"\s*local_\w+_output_modifier\s*=\s*[^\n]+\n", "", inner)
            new_lines = [f"\t{k} = {v}" for k, v in sorted(river_mods.items())]
            new_inner = inner_cleaned.rstrip() + "\n" + "\n".join(new_lines) + "\n"
            new_block = prefix + new_inner + suffix
            content = content[: m.start()] + new_block + content[m.end() :]
            print("Updated river_flowing_through in pp_location_modifier_adjustments.txt")

    # 3. Add adjacent_to_lake (new modifier)
    lake_mods = get_modifiers_for_attribute(df, "is_adjacent_to_lake")
    if lake_mods:
        if "adjacent_to_lake" in content:
            # Update existing
            pattern = r"(adjacent_to_lake\s*=\s*\{\s*game_data\s*=\s*\{[^}]+\}\s*)((?:.*?\n)*?)(\s*\})"
            m = re.search(pattern, content, re.DOTALL)
            if m:
                prefix, inner, suffix = m.group(1, 2, 3)
                new_lines = [f"\t{k} = {v}" for k, v in sorted(lake_mods.items())]
                new_inner = "\n".join(new_lines)
                new_block = prefix + new_inner + suffix
                content = content[: m.start()] + new_block + content[m.end() :]
        else:
            # Insert after river_flowing_through
            new_block = "\n"
            new_block += "adjacent_to_lake = {\n"
            new_block += "\tgame_data = {\n\t\tcategory = location\n\t}\n"
            new_block += "\n".join(f"\t{k} = {v}" for k, v in sorted(lake_mods.items())) + "\n"
            new_block += "}\n"
            # Insert after TRY_INJECT:river_flowing_through block
            insert_pattern = r"(TRY_INJECT:river_flowing_through\s*=\s*\{[^}]*(?:\{[^}]*\}[^}]*)*\})\n"
            m = re.search(insert_pattern, content, re.DOTALL)
            if m:
                pos = m.end()
                content = content[:pos] + new_block + content[pos:]
            else:
                content += "\n" + new_block
        print("Added/updated adjacent_to_lake in pp_location_modifier_adjustments.txt")

    path.write_text(content, encoding="utf-8")


def main() -> None:
    mod_path = Path(get_path("mod_path"))
    if not mod_path.exists():
        raise SystemExit(f"Mod path not found: {mod_path}")

    df = load_matrix()
    print(f"Loaded matrix: {df.shape[0]} goods x {df.shape[1]} attributes")

    update_inject_file(
        mod_path,
        "in_game/common/vegetation/pp_vegetation_changes.txt",
        VEGETATION,
        df,
    )
    update_inject_file(
        mod_path,
        "in_game/common/topography/pp_topography_changes.txt",
        TOPOGRAPHY,
        df,
    )
    update_inject_file(
        mod_path,
        "in_game/common/climates/pp_climate_changes.txt",
        CLIMATE,
        df,
    )
    update_location_modifier_adjustments(mod_path, df)
    print("Done.")


if __name__ == "__main__":
    main()
