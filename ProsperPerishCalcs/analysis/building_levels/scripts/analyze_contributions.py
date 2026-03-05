import os

import pandas as pd

from analysis.building_levels.building_analysis import CapacityAnalyzer, get_path


def main():
    game_path = get_path("game_path")
    mod_path = get_path("mod_path")
    data_dir = get_path("data_dir")

    print("Initializing analyzer with live data...")
    analyzer = CapacityAnalyzer()

    # Use analyzer's location data
    df_locations = analyzer.location_data.get_merged_df()

    building_types = ["Fruit Orchard", "Sheep Farm", "Farming Village", "Fishing Village", "Forest Village"]

    # 1. Modifier Contributions
    print("Analyzing modifier contributions...")
    contribution_results = []
    for building in building_types:
        df_detailed = analyzer.calculate_capacities_for_locations(df_locations, building_name=building)
        bonus_cols = ['Base', 'Climate Bonus', 'Topography Bonus', 'Vegetation Bonus', 'Water Bonus', 'RGO Bonus', 'Pop Bonus', 'Dev Bonus']
        existing_bonus_cols = [col for col in bonus_cols if col in df_detailed.columns]
        sums = df_detailed[existing_bonus_cols].sum()
        total_sum = sums.sum()
        percentages = (sums / total_sum * 100).round(2)
        res = {"Building": building}
        for col in existing_bonus_cols:
            res[col] = percentages[col]
        contribution_results.append(res)

    df_contrib = pd.DataFrame(contribution_results)
    df_contrib.to_csv(os.path.join(data_dir, "building_modifier_contributions.csv"), index=False)

    # 2. Attribute Value Contributions
    print("Analyzing attribute value contributions...")
    all_value_contributions = []
    data = analyzer.parser.get_all_data(mod_path)
    statics = data["static"]

    for building in building_types:
        df_detailed = analyzer.calculate_capacities_for_locations(df_locations, building_name=building)
        total_global_capacity = df_detailed['Total Bonus'].sum()

        categories = {'Climate': 'Climate Bonus', 'Topography': 'Topography Bonus', 'Vegetation': 'Vegetation Bonus', 'RGO': 'RGO Bonus', 'Rank': 'Rank Bonus'}
        for cat_name, bonus_col in categories.items():
            val_sums = df_detailed.groupby(cat_name)[bonus_col].sum()
            for val, amount in val_sums.items():
                if amount != 0:
                    all_value_contributions.append({"Building": building, "Category": cat_name, "Attribute Value": val, "Absolute Contribution": amount, "Percentage of Global Total": round((amount / total_global_capacity * 100), 2)})

        mod_key = analyzer.building_map[building]
        for cat_name, col_name, key in [('Coastal', 'Coastal', 'coastal'), ('River', 'River', 'river'), ('Lake', 'Lake', 'lake')]:
            mod_val = statics.get(key, {}).get(mod_key, 0.0)
            if mod_val != 0:
                count = (df_detailed[col_name] == key).sum()
                amount = count * mod_val
                all_value_contributions.append({"Building": building, "Category": cat_name, "Attribute Value": key, "Absolute Contribution": amount, "Percentage of Global Total": round((amount / total_global_capacity * 100), 2)})

        for cat, val_name, col in [('System', 'Base', 'Base'), ('Dynamics', 'Population', 'Pop Bonus'), ('Dynamics', 'Development', 'Dev Bonus')]:
            amount = df_detailed[col].sum()
            if amount != 0:
                all_value_contributions.append({"Building": building, "Category": cat, "Attribute Value": val_name, "Absolute Contribution": amount, "Percentage of Global Total": round((amount / total_global_capacity * 100), 2)})

    df_value_final = pd.DataFrame(all_value_contributions)
    df_value_final = df_value_final.sort_values(['Building', 'Percentage of Global Total'], ascending=[True, False])
    df_value_final.to_csv(os.path.join(data_dir, "building_attribute_value_contributions.csv"), index=False)

    print(f"Contributions exported to: {data_dir}")


if __name__ == "__main__":
    main()
