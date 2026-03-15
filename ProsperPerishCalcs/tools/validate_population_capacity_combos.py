"""
Validate that all topography + climate + vegetation combos have additive sum >= 0.

Uses plan values from Climate Floor + Topography/Vegetation Outliers.
Run: python -m tools.validate_population_capacity_combos
"""

# Plan target values (topography base 0, climate base 0, vegetation = vanilla base + inject)
TOPOGRAPHY = {
    "salt_pans": -12,
    "atoll": -6,
    "mountains": -12,
    "wetlands": 8,
    "plateau": 28,
    "hills": 51,
    "flatland": 88,
}

CLIMATE = {
    "arctic": 20,
    "cold_arid": 28,
    "arid": 38,
    "tropical": 52,
    "continental": 62,
    "oceanic": 68,
    "subtropical": 76,
    "mediterranean": 85,
}

# Vanilla base + mod inject = final
VEGETATION = {
    "desert": -8,
    "sparse": 2,
    "jungle": 12,
    "forest": 18,
    "woods": 38,
    "grasslands": 68,
    "farmland": 105,
}


def main():
    negatives = []
    min_sum = float("inf")
    min_combo = None
    max_sum = float("-inf")
    max_combo = None

    for topo_name, topo_val in TOPOGRAPHY.items():
        for clim_name, clim_val in CLIMATE.items():
            for veg_name, veg_val in VEGETATION.items():
                s = topo_val + clim_val + veg_val
                combo = (topo_name, clim_name, veg_name)
                if s < 0:
                    negatives.append((combo, s))
                if s < min_sum:
                    min_sum = s
                    min_combo = combo
                if s > max_sum:
                    max_sum = s
                    max_combo = combo

    print("Validation: topography + climate + vegetation additive sum >= 0")
    print("=" * 60)
    if negatives:
        print(f"FAIL: {len(negatives)} combos have negative sum:")
        for (topo, clim, veg), s in sorted(negatives, key=lambda x: x[1])[:20]:
            print(f"  {topo} + {clim} + {veg} = {s}")
        if len(negatives) > 20:
            print(f"  ... and {len(negatives) - 20} more")
        return 1

    print("PASS: All combos have sum >= 0")
    print(f"Worst combo:  {min_combo[0]} + {min_combo[1]} + {min_combo[2]} = {min_sum}")
    print(f"Best combo:   {max_combo[0]} + {max_combo[1]} + {max_combo[2]} = {max_sum}")
    return 0


if __name__ == "__main__":
    exit(main())
