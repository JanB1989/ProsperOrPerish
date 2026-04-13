"""Tests for apply_mining_rgo_modifiers (matrix model)."""

import pandas as pd
import pytest

from analysis.building_levels.scripts.apply_mining_rgo_modifiers import (
    IDENTITY_MATRIX_ORDER,
    MINING_GOODS_SET,
    _coerce_cell_float,
    _fmt_modifier,
    build_mining_section_text,
    read_mining_matrix,
    replace_mining_section,
)


def test_fmt_modifier_zero() -> None:
    assert _fmt_modifier(0.0) == "0"


def test_fmt_modifier_decimals() -> None:
    assert _fmt_modifier(-1.0) == "-1.00"
    assert _fmt_modifier(-0.9) == "-0.90"
    assert _fmt_modifier(0.1) == "0.10"


def test_coerce_cell_float() -> None:
    assert _coerce_cell_float(1) == 1.0
    assert _coerce_cell_float(0.1) == 0.1
    assert _coerce_cell_float("0,1") == 0.1
    assert _coerce_cell_float("1") == 1.0


def test_coerce_cell_float_bool() -> None:
    assert _coerce_cell_float(True) == 1.0
    assert _coerce_cell_float(False) == 0.0


def test_read_mining_matrix_roundtrip(tmp_path) -> None:
    n = len(IDENTITY_MATRIX_ORDER)
    data = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    df_in = pd.DataFrame(
        data, index=list(IDENTITY_MATRIX_ORDER), columns=list(IDENTITY_MATRIX_ORDER)
    )
    p = tmp_path / "m.xlsx"
    with pd.ExcelWriter(p, engine="openpyxl") as w:
        df_in.to_excel(w, sheet_name="Tabelle1")
    df_out = read_mining_matrix(p)
    assert list(df_out.index) == list(IDENTITY_MATRIX_ORDER)
    assert list(df_out.columns) == list(IDENTITY_MATRIX_ORDER)
    assert df_out.loc["coal", "coal"] == 1.0
    assert df_out.loc["coal", "iron"] == 0.0


def test_build_saltpeter_row_example() -> None:
    """Saltpeter row from user matrix: mostly 0, stone 0.1, saltpeter 1, alum 0.1."""
    order = list(IDENTITY_MATRIX_ORDER)
    row = {g: 0.0 for g in order}
    row["stone"] = 0.1
    row["saltpeter"] = 1.0
    row["alum"] = 0.1
    data = []
    for rg in order:
        data.append([1.0 if rg == cg else 0.0 for cg in order])
    df = pd.DataFrame(data, index=order, columns=order)
    for cg in order:
        df.loc["saltpeter", cg] = row[cg]
    text = build_mining_section_text(df)
    assert "pp_rgo_bonus_saltpeter = {" in text
    assert "\tlocal_coal_output_modifier = -1.00\n" in text
    assert "\tlocal_stone_output_modifier = -0.90\n" in text
    assert "\tlocal_saltpeter_output_modifier = 0\n" in text
    assert "\tlocal_alum_output_modifier = -0.90\n" in text


def test_replace_mining_section() -> None:
    before = "before\n# Mining\npp_rgo_bonus_x = {\n}\n"
    new_sec = "# Mining\npp_rgo_bonus_y = {\n\tgame_data = { category = location }\n}\n"
    after = replace_mining_section(before, new_sec)
    assert after == "before\n# Mining\npp_rgo_bonus_y = {\n\tgame_data = { category = location }\n}\n"


def test_read_rejects_wrong_size(tmp_path) -> None:
    df = pd.DataFrame([[1.0, 0], [0, 1.0]], index=["a", "b"], columns=["a", "b"])
    p = tmp_path / "bad.xlsx"
    with pd.ExcelWriter(p, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="Tabelle1")
    with pytest.raises(SystemExit):
        read_mining_matrix(p)


def test_mining_goods_count() -> None:
    assert len(MINING_GOODS_SET) == 13
    assert len(IDENTITY_MATRIX_ORDER) == 13
    assert set(IDENTITY_MATRIX_ORDER) == set(MINING_GOODS_SET)
