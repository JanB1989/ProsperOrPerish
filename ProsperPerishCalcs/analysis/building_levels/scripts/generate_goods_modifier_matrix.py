"""Generate the goods × attributes output modifier matrix as a human-editable Excel file."""

import os

import pandas as pd

from analysis.building_levels.building_analysis import get_path

# 14 goods from building capacity outputs (pp_building_capacity_values)
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

# 25 attributes: topography (7 buildable only) | vegetation (7) | climate (8) | water (3)
# Buildable topographies only: five land + salt_pans, atoll (Fishing Village). No wasteland.
TOPOGRAPHY = [
    "flatland",
    "hills",
    "plateau",
    "mountains",
    "wetlands",
    "salt_pans",
    "atoll",
]
VEGETATION = [
    "desert",
    "sparse",
    "grasslands",
    "farmland",
    "woods",
    "forest",
    "jungle",
]
CLIMATE = [
    "tropical",
    "subtropical",
    "oceanic",
    "arid",
    "cold_arid",
    "mediterranean",
    "continental",
    "arctic",
]
WATER = [
    "has_river",
    "is_adjacent_to_lake",
    "is_coastal",
]

ATTRIBUTES = TOPOGRAPHY + VEGETATION + CLIMATE + WATER


def main():
    # Build 14×32 matrix, all zeros
    matrix = {good: {attr: 0.0 for attr in ATTRIBUTES} for good in GOODS}
    df = pd.DataFrame(matrix).T

    data_dir = get_path("data_dir")
    output_path = os.path.join(data_dir, "goods_output_modifiers.xlsx")

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Matrix")
        info_df = pd.DataFrame(
            {
                "Info": [
                    "Per-cell bounds: [-0.35, 0.35]",
                    "Sum across applicable attributes (one topography + one vegetation + one climate + water bonuses if present).",
                ]
            }
        )
        info_df.to_excel(writer, sheet_name="Info", index=False)

    print(f"Matrix ({len(GOODS)} goods x {len(ATTRIBUTES)} attributes) written to {output_path}")


if __name__ == "__main__":
    main()
