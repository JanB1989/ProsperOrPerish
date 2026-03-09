import os

import pandas as pd

from analysis.building_levels.building_analysis import CapacityAnalyzer, get_path


def main():
    # Initialize analyzer
    analyzer = CapacityAnalyzer()
    
    print("Generating all theoretical combinations (Geographical only)...")
    df_combinations = analyzer.get_full_analysis_df(include_rank=False, include_rgo=False)
    
    # Pivot the DataFrame
    df_pivoted = df_combinations.pivot_table(
        index=['Climate', 'Topography', 'Vegetation', 'Coastal', 'River', 'Lake'],
        columns='Building',
        values='Total Bonus',
        aggfunc='first'
    ).reset_index()
    
    # Add the base levels (all 0)
    building_cols = ["Fruit Orchard", "Sheep Farm", "Farming Village", "Fishing Village", "Forest Village"]
    for col in building_cols:
        df_pivoted[col] = df_pivoted[col] + analyzer.base_levels[col]
    
    print(f"Generated {len(df_pivoted)} unique combinations.")
    
    # Export to CSV
    data_dir = get_path("data_dir")
    output_path = os.path.join(data_dir, "theoretical_building_combinations.csv")
    df_pivoted.to_csv(output_path, index=False)
    print(f"Combinations exported to: {output_path}")

if __name__ == "__main__":
    main()
