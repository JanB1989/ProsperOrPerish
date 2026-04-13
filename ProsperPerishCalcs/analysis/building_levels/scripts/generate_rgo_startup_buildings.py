"""
Generate Paradox `construct_building` blocks for RGO-tied startup buildings from
`pp_rgo_goods_building_sets.xlsx` (sheet `RGO_goods`).

Usage:
  uv run python -m analysis.building_levels.scripts.generate_rgo_startup_buildings
  uv run python -m analysis.building_levels.scripts.generate_rgo_startup_buildings --dry-run

Column `amount_buil` (optional in the file; defaults to 1): target total building levels when
conditions match. The script emits (1) an `if` with `construct_building` when the building is
absent, and (2) when amount > 1 a second `if` that runs `change_building_level_in_location` with a
script delta so the location reaches `amount` levels (same pattern as fruit_orchard trimming in
`pp_remove_invalid_buildings`). The second `if` is separate so the level change runs after the
building exists.

Mod integration (Prosper or Perish): the game file `pp_game_start.txt` contains a block between
`# BEGIN pp_rgo_startup_buildings` and `# END pp_rgo_startup_buildings`. After editing the Excel
sheet, regenerate and replace only that block (keep the BEGIN/END lines), or run with `-o` to a
temp file and paste the inner content.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS: tuple[str, ...] = (
    "good",
    "n_pm_outputs",
    "building_set",
    "minimum_population",
    "minimum_development",
    "rural",
    "town",
    "city",
    "startup",
    "amount_buil",
)

RANK_COLUMNS: tuple[tuple[str, str], ...] = (
    ("rural", "rural_settlement"),
    ("town", "town"),
    ("city", "city"),
)

ID_TOKEN = re.compile(r"^[a-zA-Z0-9_]+$")


def _repo_root(start: Path | None = None) -> Path:
    p = (start or Path.cwd()).resolve()
    while p != p.parent:
        if (p / "pyproject.toml").is_file():
            return p
        p = p.parent
    raise FileNotFoundError("Could not find repo root (pyproject.toml).")


def parse_yes(value: object) -> bool | None:
    """Return True/False for yes/no tokens; None if missing or unrecognized."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip().lower()
    if s in ("", "nan"):
        return None
    if s in ("yes", "y", "true", "1"):
        return True
    if s in ("no", "n", "false", "0"):
        return False
    return None


def validate_id(name: str, value: str) -> None:
    if not value:
        raise ValueError(f"{name} is empty.")
    if not ID_TOKEN.fullmatch(value):
        raise ValueError(
            f"{name} must match [a-zA-Z0-9_]+, got {value!r}."
        )


def parse_int_threshold(name: str, raw: object, *, default_if_empty: int = 0) -> int:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return default_if_empty
    if isinstance(raw, str) and not raw.strip():
        return default_if_empty
    try:
        v = int(float(raw))
    except (TypeError, ValueError) as e:
        raise ValueError(f"{name}: expected integer, got {raw!r}") from e
    return v


def parse_amount_buil(raw: object) -> int:
    """Levels to build after placement (1 = only construct_building). Default 1 if blank."""
    v = parse_int_threshold("amount_buil", raw, default_if_empty=1)
    if v < 1:
        raise ValueError(f"amount_buil: expected integer >= 1, got {v}")
    return v


def load_rgo_sheet(xlsx: Path, sheet: str) -> pd.DataFrame:
    df = pd.read_excel(xlsx, sheet_name=sheet, engine="openpyxl")
    # User-facing name in sheet may be amount_buil or amount_build (typo variants).
    if "amount_buil" not in df.columns:
        if "amount_build" in df.columns:
            df["amount_buil"] = df["amount_build"]
        else:
            df["amount_buil"] = 1
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise SystemExit(
            f"{xlsx}: sheet {sheet!r} missing columns: {missing}. "
            f"Found: {list(df.columns)}"
        )
    return df


def warn_skipped_startup_rows(df: pd.DataFrame) -> None:
    """Log warnings for startup=yes rows that produce no effects (optional plan behavior)."""
    for idx, row in df.iterrows():
        if parse_yes(row.get("startup")) is not True:
            continue
        building = row.get("building_set")
        empty_b = (
            building is None
            or (isinstance(building, float) and pd.isna(building))
            or not str(building).strip()
        )
        if empty_b:
            g = row.get("good")
            g_s = "" if g is None or (isinstance(g, float) and pd.isna(g)) else str(g).strip()
            print(
                f"warning: RGO_goods row {int(idx) + 2} (good={g_s!r}): "
                "startup=yes but building_set empty; skipped",
                file=sys.stderr,
            )
            continue
        good_raw = row.get("good")
        if good_raw is None or (isinstance(good_raw, float) and pd.isna(good_raw)):
            print(
                f"warning: RGO_goods row {int(idx) + 2}: startup=yes but good empty; skipped",
                file=sys.stderr,
            )


def iter_effects(df: pd.DataFrame) -> list[dict[str, object]]:
    """Return sorted list of effect specs: good, building, rank_key, min_pop, use_dev, min_dev, amount."""
    effects: list[dict[str, object]] = []
    for _idx, row in df.iterrows():
        if parse_yes(row.get("startup")) is not True:
            continue
        building = row.get("building_set")
        if building is None or (isinstance(building, float) and pd.isna(building)):
            continue
        building_str = str(building).strip()
        if not building_str:
            continue
        validate_id("building_set", building_str)

        good_raw = row.get("good")
        if good_raw is None or (isinstance(good_raw, float) and pd.isna(good_raw)):
            continue
        good = str(good_raw).strip()
        validate_id("good", good)

        try:
            amount = parse_amount_buil(row.get("amount_buil"))
        except ValueError as e:
            raise ValueError(f"row good={good!r}: {e}") from e

        min_pop = parse_int_threshold("minimum_population", row.get("minimum_population"))
        min_dev_raw = row.get("minimum_development")
        min_dev = parse_int_threshold(
            "minimum_development", min_dev_raw, default_if_empty=0
        )
        use_dev = min_dev > 0

        for col, rank_key in RANK_COLUMNS:
            if parse_yes(row.get(col)) is not True:
                continue
            effects.append(
                {
                    "good": good,
                    "building": building_str,
                    "rank_key": rank_key,
                    "min_pop": min_pop,
                    "use_dev": use_dev,
                    "min_dev": min_dev,
                    "amount": amount,
                }
            )

    rank_order = {"rural_settlement": 0, "town": 1, "city": 2}
    effects.sort(key=lambda e: (str(e["good"]), rank_order[e["rank_key"]]))
    return effects


def render_game_start_snippet(
    effects: list[dict[str, object]], *, source_comment: str
) -> str:
    lines: list[str] = [
        f"\t\t\t\t# pp_rgo_startup_buildings (generated) - {source_comment}",
    ]
    for e in effects:
        good = str(e["good"])
        building = str(e["building"])
        rank_key = str(e["rank_key"])
        min_pop = int(e["min_pop"])
        use_dev = bool(e["use_dev"])
        min_dev = int(e["min_dev"])
        amount = int(e["amount"])

        limit_lines = [
            f"\t\t\t\t\t\traw_material = goods:{good}",
            f"\t\t\t\t\t\tlocation_rank = location_rank:{rank_key}",
            f"\t\t\t\t\t\tpopulation > {min_pop}",
        ]
        if use_dev:
            limit_lines.append(f"\t\t\t\t\t\tdevelopment > {min_dev}")
        limit_lines.append(
            f"\t\t\t\t\t\tNOT = {{ has_building = building_type:{building} }}"
        )

        # Block 1: place first level (must be separate from level-up — same-scope effects
        # can run before the building exists for change_building_level_in_location).
        lines.append("\t\t\t\tif = {")
        lines.append("\t\t\t\t\tlimit = {")
        lines.extend(limit_lines)
        lines.append("\t\t\t\t\t}")
        lines.append("\t\t\t\t\tconstruct_building = {")
        lines.append(f"\t\t\t\t\t\tbuilding_type = building_type:{building}")
        lines.append("\t\t\t\t\t\tinstant = yes")
        lines.append("\t\t\t\t\t\tcost_multiplier = 0")
        lines.append('\t\t\t\t\t\tcost_multiplier_reason = "game_start"')
        lines.append("\t\t\t\t\t}")
        lines.append("\t\t\t\t}")

        if amount > 1:
            limit_up = [
                f"\t\t\t\t\t\traw_material = goods:{good}",
                f"\t\t\t\t\t\tlocation_rank = location_rank:{rank_key}",
                f"\t\t\t\t\t\tpopulation > {min_pop}",
            ]
            if use_dev:
                limit_up.append(f"\t\t\t\t\t\tdevelopment > {min_dev}")
            limit_up.append(
                f"\t\t\t\t\t\thas_building = building_type:{building}"
            )
            limit_up.append("\t\t\t\t\t\tlocation_building_level = {")
            limit_up.append(f"\t\t\t\t\t\t\tbuilding_type = building_type:{building}")
            limit_up.append(f"\t\t\t\t\t\t\tvalue < {amount}")
            limit_up.append("\t\t\t\t\t\t}")

            lines.append("\t\t\t\tif = {")
            lines.append("\t\t\t\t\tlimit = {")
            lines.extend(limit_up)
            lines.append("\t\t\t\t\t}")
            lines.append("\t\t\t\t\tchange_building_level_in_location = {")
            lines.append(f"\t\t\t\t\t\tbuilding = building_type:{building}")
            lines.append("\t\t\t\t\t\tvalue = {")
            lines.append(f"\t\t\t\t\t\t\tvalue = {amount}")
            lines.append("\t\t\t\t\t\t\tadd = {")
            lines.append(
                f"\t\t\t\t\t\t\t\tvalue = \"location_building_level(building_type:{building})\""
            )
            lines.append("\t\t\t\t\t\t\t\tmultiply = -1")
            lines.append("\t\t\t\t\t\t\t}")
            lines.append("\t\t\t\t\t\t}")
            lines.append("\t\t\t\t\t}")
            lines.append("\t\t\t\t}")
    return "\n".join(lines) + "\n"


def dry_run_summary(df: pd.DataFrame, effects: list[dict[str, object]]) -> str:
    n_rows = len(df)
    startup_yes = sum(1 for _, r in df.iterrows() if parse_yes(r.get("startup")) is True)
    nonempty_building = sum(
        1
        for _, r in df.iterrows()
        if parse_yes(r.get("startup")) is True
        and str(r.get("building_set") or "").strip()
        and not (
            isinstance(r.get("building_set"), float) and pd.isna(r.get("building_set"))
        )
    )
    return (
        f"rows={n_rows} startup_yes~{startup_yes} "
        f"startup+nonempty_building~{nonempty_building} generated_effects={len(effects)}\n"
    )


def main(argv: list[str] | None = None) -> int:
    root = _repo_root()
    default_xlsx = (
        root / "analysis" / "building_levels" / "data" / "pp_rgo_goods_building_sets.xlsx"
    )

    p = argparse.ArgumentParser(
        description="Emit Paradox startup building blocks from pp_rgo_goods_building_sets.xlsx."
    )
    p.add_argument("--xlsx", type=Path, default=default_xlsx, help="Path to workbook")
    p.add_argument(
        "--sheet", default="RGO_goods", help="Worksheet name (default: RGO_goods)"
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Write to this file (default: stdout)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print counts only, do not emit script",
    )
    args = p.parse_args(argv)

    xlsx: Path = args.xlsx.resolve()
    if not xlsx.is_file():
        print(f"error: file not found: {xlsx}", file=sys.stderr)
        return 1

    df = load_rgo_sheet(xlsx, args.sheet)
    warn_skipped_startup_rows(df)
    try:
        effects = iter_effects(df)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if args.dry_run:
        sys.stdout.write(dry_run_summary(df, effects))
        return 0

    rel = xlsx
    try:
        rel = xlsx.relative_to(root)
    except ValueError:
        pass
    snippet = render_game_start_snippet(
        effects, source_comment=f"from {rel}"
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(snippet, encoding="utf-8")
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(snippet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
