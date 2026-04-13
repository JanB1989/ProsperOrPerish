"""Tests for parse / surgical write of pp_rgo_static_bonuses.txt."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from analysis.building_levels.scripts.pp_rgo_static_bonuses_io import (
    apply_pp_rgo_static_bonuses,
    local_output_key,
    parse_pp_rgo_static_bonuses,
)


def test_local_output_key_goods_gold() -> None:
    assert local_output_key("goods_gold") == "local_goods_gold_output_modifier"
    assert local_output_key("wheat") == "local_wheat_output_modifier"


def test_parse_normal_peasants_and_goods_gold(tmp_path: Path) -> None:
    p = tmp_path / "pp_rgo_static_bonuses.txt"
    p.write_text(
        """pp_rgo_bonus_wheat = {
\tgame_data = { category = location }
\tlocal_wheat_output_modifier = 0.10
\tlocal_peasants_food_consumption = -0.08
}

pp_rgo_bonus_goods_gold = {
\tgame_data = { category = location }
\tlocal_goods_gold_output_modifier = 0.10
}
""",
        encoding="utf-8",
    )
    df = parse_pp_rgo_static_bonuses(p)
    assert df.loc["wheat", "output_modifier"] == pytest.approx(0.10)
    assert df.loc["wheat", "peasants_food"] == pytest.approx(-0.08)
    assert df.loc["goods_gold", "output_modifier"] == pytest.approx(0.10)
    assert pd.isna(df.loc["goods_gold", "peasants_food"])


def test_parse_block_without_output_line(tmp_path: Path) -> None:
    p = tmp_path / "pp_rgo_static_bonuses.txt"
    p.write_text(
        """pp_rgo_bonus_dyes = {
\tgame_data = { category = location }
}
""",
        encoding="utf-8",
    )
    df = parse_pp_rgo_static_bonuses(p)
    assert "dyes" in df.index
    assert pd.isna(df.loc["dyes", "output_modifier"])
    assert pd.isna(df.loc["dyes", "peasants_food"])


def test_roundtrip_preserves_values(tmp_path: Path) -> None:
    p = tmp_path / "pp_rgo_static_bonuses.txt"
    p.write_text(
        """pp_rgo_bonus_fruit = {
\tgame_data = { category = location }
\tlocal_fruit_output_modifier = 0.10
\tlocal_peasants_food_consumption = -0.04
}

pp_rgo_bonus_dyes = {
\tgame_data = { category = location }
}
""",
        encoding="utf-8",
    )
    df = parse_pp_rgo_static_bonuses(p)
    apply_pp_rgo_static_bonuses(p, df)
    df2 = parse_pp_rgo_static_bonuses(p)
    pd.testing.assert_frame_equal(df, df2)


def test_apply_updates_value(tmp_path: Path) -> None:
    p = tmp_path / "pp_rgo_static_bonuses.txt"
    p.write_text(
        """pp_rgo_bonus_fruit = {
\tgame_data = { category = location }
\tlocal_fruit_output_modifier = 0.10
}
""",
        encoding="utf-8",
    )
    df = parse_pp_rgo_static_bonuses(p)
    df.loc["fruit", "output_modifier"] = 0.25
    apply_pp_rgo_static_bonuses(p, df)
    df2 = parse_pp_rgo_static_bonuses(p)
    assert df2.loc["fruit", "output_modifier"] == pytest.approx(0.25)


def test_apply_rejects_unknown_good(tmp_path: Path) -> None:
    p = tmp_path / "pp_rgo_static_bonuses.txt"
    p.write_text(
        """pp_rgo_bonus_fruit = {
\tgame_data = { category = location }
\tlocal_fruit_output_modifier = 0.10
}
""",
        encoding="utf-8",
    )
    df = pd.DataFrame(
        {"output_modifier": [0.1], "peasants_food": [float("nan")]},
        index=["nonexistent_good"],
    )
    with pytest.raises(ValueError, match="No block"):
        apply_pp_rgo_static_bonuses(p, df)
