import os

import pandas as pd

from analysis.building_levels.building_analysis import CapacityAnalyzer, get_path


def main():
    print("Initializing analyzer with live data...")
    analyzer = CapacityAnalyzer()

    print("Loading locations...")
    df_locations = analyzer.location_data.get_merged_df()

    # Pre-process water statuses
    df_locations['Coastal'] = df_locations['is_coastal'].map({'yes': 'coastal', 'no': 'non_coastal'}).fillna('non_coastal')

    if 'has_river' not in df_locations.columns:
        df_locations['has_river'] = 'no'
    if 'is_adjacent_to_lake' not in df_locations.columns:
        df_locations['is_adjacent_to_lake'] = 'no'

    df_locations['River'] = df_locations['has_river'].map({'yes': 'river', 'no': 'non_river'}).fillna('non_river')
    df_locations['Lake'] = df_locations['is_adjacent_to_lake'].map({'yes': 'lake', 'no': 'non_lake'}).fillna('non_lake')

    df_locations = df_locations.rename(columns={
        'climate': 'Climate',
        'topography': 'Topography',
        'vegetation': 'Vegetation'
    })

    print("Identifying unique existing combinations...")
    geo_factors = ['Climate', 'Topography', 'Vegetation', 'Coastal', 'River', 'Lake']
    df_counts = df_locations.groupby(geo_factors).size().reset_index(name='Location Count')

    print(f"Found {len(df_counts)} unique geographical combinations in the game.")

    # Dummy locations for analyzer
    dummy_locations = df_counts.copy()
    dummy_locations['location'] = 'dummy'
    dummy_locations['rank'] = 'rural_settlement'
    dummy_locations = dummy_locations.rename(columns={
        'Climate': 'climate',
        'Topography': 'topography',
        'Vegetation': 'vegetation',
        'Coastal': 'is_coastal',
        'River': 'has_river',
        'Lake': 'is_adjacent_to_lake'
    })
    dummy_locations['is_coastal'] = dummy_locations['is_coastal'].map({'coastal': 'yes', 'non_coastal': 'no'})
    dummy_locations['has_river'] = dummy_locations['has_river'].map({'river': 'yes', 'non_river': 'no'})
    dummy_locations['is_adjacent_to_lake'] = dummy_locations['is_adjacent_to_lake'].map({'lake': 'yes', 'non_lake': 'no'})

    print("Calculating capacities for existing combinations...")
    df_capacities = analyzer.calculate_capacities_for_locations(dummy_locations)

    # Pivot
    df_pivoted = df_capacities.pivot_table(
        index=geo_factors,
        columns='Building',
        values='Total Bonus',
        aggfunc='first'
    ).reset_index()

    # Merge with count
    df_final = df_pivoted.merge(df_counts, on=geo_factors)
    df_final = df_final.sort_values('Location Count', ascending=False)

    data_dir = get_path("data_dir")
    output_path = os.path.join(data_dir, "actual_building_combinations.csv")
    df_final.to_csv(output_path, index=False)
    print(f"Actual combinations exported to: {output_path}")


if __name__ == "__main__":
    main()
