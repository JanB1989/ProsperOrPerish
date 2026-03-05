# Data Modules

Specialized modules for managing game entities, adhering to the "Vanilla as Gospel" principle.

## Core Principles

1.  **Vanilla as Gospel**: All data resolution starts with the base game files. This base state is fully resolved (including cross-references) before any modded adjustments are applied.
2.  **Folder Discovery**: Parsers scan multiple directories to form a complete entity profile. For example, goods data is aggregated from:
    - `common/goods`
    - `common/goods_demand`
    - `common/goods_demand_category`
3.  **Data Integrity**: Economic fields like `transport_cost`, `default_market_price`, and `method` are never defaulted or invented. They must be resolved from the actual game scripts or the engine's hardcoded defaults (e.g., `transport_cost = 1.0`, `default_market_price = 1.0`, `method = farming`).
4.  **Deep Merging**: Modded adjustments (`INJECT`, `REPLACE`) are applied via deep update logic to ensure complex nested blocks (like `pop_demand`) are merged correctly.

## Modules

- `location_data.py`: Manages location hierarchies, population data, and development calculations.
- `goods_data.py`: Resolves economic profiles for all goods, cross-referencing demand scripts and categories to find `transport_cost` and `food` values.
- `building_data.py`: Manages building definitions and production method slots, supporting side-by-side vanilla/modded comparisons. Extracts and resolves population employment data (`pop_type`, `employment_size`) in game "per 1k" units. Building modifier output (`local_monthly_food`) is valued at defines `FOOD_PRICE`, not market price.
- `goods_demand_data.py`: Helper module for parsing complex demand structures.
- `defines_data.py`: Manages game defines (e.g., `FOOD_PRICE`) from `loading_screen/common/defines`.
- `pop_data.py`: Manages pop types and their properties (e.g., `pop_food_consumption`).
