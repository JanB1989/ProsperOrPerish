"""Clamp goods output modifier matrix values to [-0.35, 0.35] and save back to Excel.

Run: uv run python -m analysis.building_levels.scripts.clamp_goods_modifiers
"""

from __future__ import annotations

import os

import pandas as pd

from analysis.building_levels.building_analysis import get_path, load_goods_output_modifiers

MIN_VAL = -0.35
MAX_VAL = 0.35


def main() -> None:
    data_dir = get_path("data_dir")
    path = os.path.join(data_dir, "goods_output_modifiers.xlsx")

    df = load_goods_output_modifiers(path=path, validate=False)

    min_before = df.min().min()
    max_before = df.max().max()
    clamped_count = 0

    for col in df.columns:
        for idx in df.index:
            val = df.loc[idx, col]
            if pd.isna(val):
                continue
            v = float(val)
            original_rounded = round(v, 2)
            clamped = max(MIN_VAL, min(MAX_VAL, v))
            rounded = round(clamped, 2)
            if original_rounded != rounded:
                clamped_count += 1
            df.loc[idx, col] = rounded

    # Ensure all values are properly rounded (handle any float precision issues)
    df = df.round(2)

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Matrix")
        info_df = pd.DataFrame(
            {
                "Info": [
                    "Per-cell bounds: [-0.35, 0.35]",
                    "Sum across applicable attributes. Values clamped and rounded to 2 decimals.",
                ]
            }
        )
        info_df.to_excel(writer, sheet_name="Info", index=False)

    min_after = df.min().min()
    max_after = df.max().max()

    print(f"Clamped matrix saved to {path}")
    print(f"Range before: {min_before:.2f} to {max_before:.2f}")
    print(f"Range after:  {min_after:.2f} to {max_after:.2f}")
    print(f"Cells modified: {clamped_count}")


if __name__ == "__main__":
    main()
