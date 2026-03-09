import json
import os

import pandas as pd


def load_config():
    """Loads the configuration from config.json."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config.json")
    with open(config_path, "r") as f:
        config = json.load(f)
    
    # Resolve relative paths relative to base_dir
    resolved_config = {}
    for key, value in config.items():
        if key.endswith("_dir") or key == "analysis_dir":
            if not os.path.isabs(value):
                resolved_config[key] = os.path.abspath(os.path.join(base_dir, value))
            else:
                resolved_config[key] = value
        else:
            resolved_config[key] = value
    return resolved_config

def get_path(key):
    """Returns a path from the configuration."""
    config = load_config()
    return config.get(key)


def load_goods_output_modifiers(path=None, validate=True):
    """
    Load the goods × attributes output modifier matrix from Excel (.xlsx only).

    Returns a DataFrame with good as index and attribute names as columns.
    Excel is the sole source of truth; CSV is not supported.

    Args:
        path: Path to goods_output_modifiers.xlsx. If None, uses data_dir.
        validate: If True, raises ValueError if any cell is outside [-0.35, 0.35].

    Returns:
        pd.DataFrame with index=goods, columns=attributes.
    """
    if path is None:
        data_dir = get_path("data_dir")
        path = os.path.join(data_dir, "goods_output_modifiers.xlsx")

    df = pd.read_excel(path, sheet_name="Matrix", index_col=0)

    if validate:
        min_val = df.min().min()
        max_val = df.max().max()
        if min_val < -0.35 or max_val > 0.35:
            raise ValueError(
                f"Matrix has values outside bounds [-0.35, 0.35]: min={min_val}, max={max_val}"
            )

    return df
