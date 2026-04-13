"""
Apply mining RGO output modifiers from mining.xlsx into pp_rgo_static_bonuses.txt.

Spreadsheet convention (first sheet): a square matrix.
  - Row labels (column A): mining good id for pp_rgo_bonus_<row>.
  - Column labels (row 1): mining good id for local_<col>_output_modifier.
  - Cell M[r,c]: weight in [0,1]; written modifier is M[r,c] - 1
    (0 -> -1, 0.1 -> -0.9, 1 -> 0).

Each pp_rgo_bonus_<row> block lists all columns in sheet column order.

Use --init-template to write a 13x13 identity matrix (diagonal 1, else 0).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

# Expected mining goods (set equality with sheet labels; order comes from the file).
MINING_GOODS_SET: frozenset[str] = frozenset(
    {
        "alum",
        "coal",
        "copper",
        "gems",
        "goods_gold",
        "iron",
        "lead",
        "marble",
        "mercury",
        "saltpeter",
        "silver",
        "stone",
        "tin",
    }
)

# Row/column order for --init-template (matches common spreadsheet layout).
IDENTITY_MATRIX_ORDER: tuple[str, ...] = (
    "coal",
    "iron",
    "copper",
    "goods_gold",
    "silver",
    "stone",
    "tin",
    "lead",
    "gems",
    "saltpeter",
    "alum",
    "marble",
    "mercury",
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_mod_static_path() -> Path:
    cfg = _project_root() / "analysis" / "building_levels" / "config.json"
    data = json.loads(cfg.read_text(encoding="utf-8"))
    mod = Path(data["mod_path"])
    return mod / "in_game" / "common" / "static_modifiers" / "pp_rgo_static_bonuses.txt"


def _normalize_label(x: object) -> str:
    if pd.isna(x):
        return ""
    return str(x).strip()


def _coerce_cell_float(x: object) -> float:
    if pd.isna(x):
        raise ValueError("missing matrix cell")
    if isinstance(x, bool):
        return 1.0 if x else 0.0
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace(",", ".").replace(" ", "")
    if not s:
        raise ValueError("empty cell")
    return float(s)


def _fmt_modifier(v: float) -> str:
    """Two-decimal strings; zero prints as 0."""
    s = f"{v:.2f}"
    if s in ("-0.00", "0.00"):
        return "0"
    return s


def read_mining_matrix(xlsx: Path) -> pd.DataFrame:
    df = pd.read_excel(xlsx, sheet_name=0, index_col=0, header=0)
    if df.empty:
        raise SystemExit(f"{xlsx}: matrix is empty.")

    df.index = df.index.map(_normalize_label)
    df.columns = df.columns.map(_normalize_label)

    if df.index.duplicated().any():
        dup = df.index[df.index.duplicated()].tolist()
        raise SystemExit(f"{xlsx}: duplicate row labels: {dup}")
    if df.columns.duplicated().any():
        dup = df.columns[df.columns.duplicated()].tolist()
        raise SystemExit(f"{xlsx}: duplicate column labels: {dup}")

    df = df.map(_coerce_cell_float)

    idx_set = set(df.index)
    col_set = set(df.columns)
    if idx_set != col_set:
        raise SystemExit(
            f"{xlsx}: row and column label sets differ.\n"
            f"  only in rows: {idx_set - col_set}\n"
            f"  only in cols: {col_set - idx_set}"
        )
    if idx_set != MINING_GOODS_SET:
        raise SystemExit(
            f"{xlsx}: labels must be exactly {sorted(MINING_GOODS_SET)}; got {sorted(idx_set)}"
        )

    n = len(MINING_GOODS_SET)
    if df.shape != (n, n):
        raise SystemExit(
            f"{xlsx}: expected {n}x{n} matrix, got {df.shape[0]}x{df.shape[1]}"
        )

    return df


def build_mining_section_text(df: pd.DataFrame) -> str:
    parts: list[str] = []
    for row_good in df.index:
        parts.append("# Mining\n")
        parts.append(f"pp_rgo_bonus_{row_good} = {{\n")
        parts.append("\tgame_data = { category = location }\n")
        for col_good in df.columns:
            raw = float(df.loc[row_good, col_good])
            mod = raw - 1.0
            parts.append(
                f"\tlocal_{col_good}_output_modifier = {_fmt_modifier(mod)}\n"
            )
        parts.append("}\n\n")
    return "".join(parts)


def replace_mining_section(full_text: str, new_mining_section: str) -> str:
    marker = "# Mining\n"
    idx = full_text.find(marker)
    if idx == -1:
        raise SystemExit("Could not find '# Mining' section start in static modifiers file.")
    return full_text[:idx] + new_mining_section.rstrip() + "\n"


def write_identity_template(xlsx: Path) -> None:
    n = len(IDENTITY_MATRIX_ORDER)
    if n != len(MINING_GOODS_SET):
        raise SystemExit("IDENTITY_MATRIX_ORDER must list all mining goods once.")
    data = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    df = pd.DataFrame(
        data, index=list(IDENTITY_MATRIX_ORDER), columns=list(IDENTITY_MATRIX_ORDER)
    )
    xlsx.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(xlsx, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="Tabelle1")
    print(f"Wrote identity matrix template: {xlsx}")


def main() -> None:
    root = _project_root()
    default_xlsx = root / "analysis" / "building_levels" / "data" / "mining.xlsx"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--xlsx",
        type=Path,
        default=default_xlsx,
        help="Path to mining.xlsx (square matrix)",
    )
    parser.add_argument(
        "--static-modifiers",
        type=Path,
        default=None,
        help="pp_rgo_static_bonuses.txt (default: from config.json mod_path)",
    )
    parser.add_argument(
        "--init-template",
        action="store_true",
        help="Write 13x13 identity matrix to --xlsx, then exit.",
    )
    args = parser.parse_args()

    if args.init_template:
        write_identity_template(args.xlsx.resolve())
        sys.exit(0)

    static = (
        args.static_modifiers.resolve()
        if args.static_modifiers
        else _load_mod_static_path()
    )
    df = read_mining_matrix(args.xlsx.resolve())
    section = build_mining_section_text(df)
    text = static.read_text(encoding="utf-8")
    updated = replace_mining_section(text, section)
    static.write_text(updated, encoding="utf-8", newline="\n")
    print(f"Updated {static}")
    print(f"  matrix order: rows/cols = {list(df.index)}")


if __name__ == "__main__":
    main()
