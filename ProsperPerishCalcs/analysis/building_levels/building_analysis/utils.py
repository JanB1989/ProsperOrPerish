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


def load_rgo_modifiers(path=None):
    """
    Load optional sheet ``RGO`` from the same workbook as the attribute matrix
    (good_id index, columns output_modifier, peasants_food).

    If the workbook has no ``RGO`` sheet, returns an empty DataFrame with those columns.
    """
    if path is None:
        data_dir = get_path("data_dir")
        path = os.path.join(data_dir, "goods_output_modifiers.xlsx")

    try:
        return pd.read_excel(path, sheet_name="RGO", index_col=0)
    except ValueError:
        return pd.DataFrame(columns=["output_modifier", "peasants_food"])


def save_goods_and_rgo_matrices(df, rgo_df=None, path=None):
    """
    Write sheet ``Matrix`` (attribute matrix) and optionally ``RGO`` to goods_output_modifiers.xlsx.

    If ``rgo_df`` is None and the workbook already exists, any existing ``RGO`` sheet is read
    and written back so it is not dropped when only the Matrix changes.
    """
    if path is None:
        data_dir = get_path("data_dir")
        path = os.path.join(data_dir, "goods_output_modifiers.xlsx")

    if rgo_df is None and os.path.isfile(path):
        try:
            rgo_df = pd.read_excel(path, sheet_name="RGO", index_col=0)
        except ValueError:
            rgo_df = None

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Matrix")
        if rgo_df is not None:
            rgo_df.to_excel(writer, sheet_name="RGO")
