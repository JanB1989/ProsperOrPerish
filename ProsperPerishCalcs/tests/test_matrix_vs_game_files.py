"""Compare the Excel goods modifier matrix with modifiers parsed from game files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from analysis.building_levels.building_analysis import get_path, load_goods_output_modifiers
from analysis.building_levels.scripts.generate_goods_modifier_matrix import (
    ATTRIBUTES,
    GOODS,
)
from analysis.building_levels.scripts.import_modifiers_from_game_files import (
    matrix_from_mod_files,
    parse_all_mod_files,
)

TOLERANCE = 0.01


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


def test_matrix_from_mod_files_shape():
    """Imported matrix matches GOODS × ATTRIBUTES dimensions."""
    mod_path = Path(get_path("mod_path"))
    if not mod_path.exists():
        pytest.skip(f"Mod path not found: {mod_path}")

    df = matrix_from_mod_files(mod_path)
    assert list(df.index) == GOODS
    assert list(df.columns) == ATTRIBUTES
