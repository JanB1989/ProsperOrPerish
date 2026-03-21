"""Regression: unique_production_methods lists must zip-merge, not concatenate."""

from core.data.base_data import DataModule


def test_merge_unique_production_methods_same_length_zips():
    dm = DataModule.__new__(DataModule)
    base = [{"meal_a": {"rice": 1.0}}, {"drink_a": {"beer": 1.0}}]
    override = [{"meal_a": {"rice": 2.0}}, {"drink_a": {"wine": 1.0}}]
    out = dm._merge_unique_production_methods(base, override)
    assert len(out) == 2
    assert out[0]["meal_a"]["rice"] == 2.0
    # Same PM id in slot: deep_merge keeps keys from both sides when they differ
    assert out[1]["drink_a"]["wine"] == 1.0
    assert out[1]["drink_a"]["beer"] == 1.0


def test_merge_unique_production_methods_different_length_override_wins():
    dm = DataModule.__new__(DataModule)
    base = [{"a": {}}]
    override = [{"x": {}}, {"y": {}}]
    out = dm._merge_unique_production_methods(base, override)
    assert len(out) == 2
    assert "x" in out[0] and "y" in out[1]


def test_merge_unique_production_methods_dict_normalizes_to_one_slot():
    dm = DataModule.__new__(DataModule)
    base = {"only": {"k": 1}}
    override = [{"s0": {"z": 1}}, {"s1": {"w": 1}}]
    out = dm._merge_unique_production_methods(base, override)
    assert len(out) == 2
