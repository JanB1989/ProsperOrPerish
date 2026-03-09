"""Tests for the goods × attributes output modifier matrix."""

import pytest

from analysis.building_levels.building_analysis import load_goods_output_modifiers
from analysis.building_levels.scripts.generate_goods_modifier_matrix import (
    GOODS,
    ATTRIBUTES,
)


EXPECTED_GOODS = 14
EXPECTED_ATTRIBUTES = 25


def test_matrix_dimensions():
    """Matrix must be 14 goods (rows) × 25 attributes (columns)."""
    df = load_goods_output_modifiers()
    assert df.shape[0] == EXPECTED_GOODS, f"Expected {EXPECTED_GOODS} goods (rows), got {df.shape[0]}"
    assert df.shape[1] == EXPECTED_ATTRIBUTES, (
        f"Expected {EXPECTED_ATTRIBUTES} attributes (columns), got {df.shape[1]}"
    )


def test_matrix_index_and_columns_match_constants():
    """Matrix index and columns must match GOODS and ATTRIBUTES from generator."""
    df = load_goods_output_modifiers()
    assert list(df.index) == GOODS, f"Index mismatch: expected {GOODS}"
    assert list(df.columns) == ATTRIBUTES, f"Columns mismatch: expected {ATTRIBUTES}"


def test_matrix_values_in_bounds():
    """All cells must be within [-0.35, 0.35]."""
    df = load_goods_output_modifiers(validate=True)
    min_val = df.min().min()
    max_val = df.max().max()
    assert min_val >= -0.35, f"Minimum value {min_val} below -0.35"
    assert max_val <= 0.35, f"Maximum value {max_val} above 0.35"
