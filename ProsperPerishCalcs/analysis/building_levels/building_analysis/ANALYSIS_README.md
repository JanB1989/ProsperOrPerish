# Building Analysis Package

Specialized tools for analyzing EUV building capacities and economics.

## Components

- `analyzer.py`: Generalized filtering and statistical analysis engine for building data.
- `utils.py`: Configuration and path management, loading `config.json`.

## Analysis Workflow

1. **Load Data**: Uses `core/data/` modules to fetch resolved vanilla and modded data.
2. **Filter & Process**: Uses `analyzer.py` to isolate specific building types or production methods.
3. **Compare**: Generates side-by-side comparisons of economic output, input costs, and capacity utilization.
