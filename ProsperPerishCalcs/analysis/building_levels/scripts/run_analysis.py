import argparse
import os

import pandas as pd

from analysis.building_levels.building_analysis import CapacityAnalyzer, get_path


def main():
    parser = argparse.ArgumentParser(description="Run generalized building capacity analysis.")
    parser.add_argument("--mode", choices=["standard", "outlier"], default="standard", help="Analysis mode")
    parser.add_argument("--group_by", default="region", help="Column to group by (standard mode)")
    parser.add_argument("--super_region", help="Filter by super region")
    parser.add_argument("--region", help="Filter by region")
    parser.add_argument("--building", help="Specific building to analyze (required for outlier mode)")
    parser.add_argument("--top_n", type=int, default=15, help="Number of top results to show")

    args = parser.parse_args()

    print("Initializing analyzer with live data...")
    analyzer = CapacityAnalyzer()

    print("Loading locations...")
    df_locations = analyzer.location_data.get_merged_df()

    # Prepare filters
    filters = {}
    if args.super_region:
        filters['super_region'] = args.super_region
    if args.region:
        filters['region'] = args.region

    if args.mode == "standard":
        print(f"Running standard analysis grouped by {args.group_by}...")
        results = analyzer.run_standard_analysis(df_locations, group_by=args.group_by, filters=filters, top_n=args.top_n)

        for building, data in results.items():
            print(f"\n{'='*60}")
            print(f"Top {args.group_by.capitalize()}s for {building}:")
            print(f"{'='*60}")
            print(data[['Total Bonus_mean', 'Location Count']])

    elif args.mode == "outlier":
        if not args.building:
            print("Error: --building is required for outlier mode.")
            return

        print(f"Running outlier analysis for {args.building}...")
        top, bottom = analyzer.get_outlier_analysis(df_locations, building_name=args.building, filters=filters, top_n=args.top_n)

        print(f"\n--- TOP {args.top_n} LOCATIONS ---")
        print(top[['Location', 'Province', 'Region', 'Total Bonus', 'Climate', 'Topography', 'Vegetation']])

        print(f"\n--- BOTTOM {args.top_n} LOCATIONS (Non-Zero) ---")
        print(bottom[['Location', 'Province', 'Region', 'Total Bonus', 'Climate', 'Topography', 'Vegetation']])


if __name__ == "__main__":
    main()
