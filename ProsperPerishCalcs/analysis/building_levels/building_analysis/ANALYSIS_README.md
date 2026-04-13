# Building Analysis Package

Specialized tools for analyzing EUV building capacities and economics.

## Components

- `analyzer.py`: Generalized filtering and statistical analysis engine for building data.
- `utils.py`: Configuration and path management, loading `config.json`.

## Notebooks

- `notebooks/building_pm_io_matrix.ipynb`: wide `i_*` / `o_*` matrix with **merged** game+mod data (`build_pm_io_matrix(..., merged=True)`).
- `notebooks/building_pm_io_matrix_vanilla.ipynb`: same matrix using **vanilla-only** definitions (`merged=False`).

## Analysis Workflow

1. **Load Data**: Uses `core/data/` modules to fetch resolved vanilla and modded data.
2. **Filter & Process**: Uses `analyzer.py` to isolate specific building types or production methods.
3. **Compare**: Generates side-by-side comparisons of economic output, input costs, and capacity utilization.
