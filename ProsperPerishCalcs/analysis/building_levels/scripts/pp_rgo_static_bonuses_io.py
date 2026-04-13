"""Parse and surgically update pp_rgo_static_bonuses.txt (per-good RGO static modifiers)."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


def _extract_inner_block(content: str, start: int) -> tuple[str, int] | None:
    """Extract content of first {...} starting at start. Returns (inner_content, end_after_brace)."""
    if start >= len(content) or content[start] != "{":
        return None
    depth = 0
    i = start
    while i < len(content):
        if content[i] == "{":
            depth += 1
        elif content[i] == "}":
            depth -= 1
            if depth == 0:
                return content[start + 1 : i], i + 1
        i += 1
    return None


def local_output_key(good: str) -> str:
    """Game modifier key for local output of a raw material good."""
    if good == "goods_gold":
        return "local_goods_gold_output_modifier"
    return f"local_{good}_output_modifier"


_OUTPUT_LINE_RE = re.compile(
    r"^\s*local_(?:goods_gold|\w+)_output_modifier\s*=\s*[\d.-]+\s*$"
)
_PEASANTS_LINE_RE = re.compile(r"^\s*local_peasants_food_consumption\s*=\s*[\d.-]+\s*$")


def _fmt_scalar(x: float) -> str:
    s = f"{float(x):.6f}".rstrip("0").rstrip(".")
    if s == "-0":
        s = "0.0"
    return s


def parse_pp_rgo_static_bonuses(path: Path | str) -> pd.DataFrame:
    """
    Read each pp_rgo_bonus_<good> block; return DataFrame index=good_id,
    columns output_modifier, peasants_food (NaN if absent).
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    rows: list[dict[str, float | None]] = []
    output_re = re.compile(
        r"^\s*(local_(?:goods_gold|\w+)_output_modifier)\s*=\s*([\d.-]+)\s*$"
    )
    peasants_re = re.compile(r"^\s*local_peasants_food_consumption\s*=\s*([\d.-]+)\s*$")

    for m in re.finditer(r"^pp_rgo_bonus_(\w+)\s*=\s*\{", text, re.MULTILINE):
        good_id = m.group(1)
        open_brace = m.end() - 1
        inner_t = _extract_inner_block(text, open_brace)
        if inner_t is None:
            continue
        inner, _ = inner_t
        out_val: float | None = None
        peas_val: float | None = None
        for line in inner.split("\n"):
            om = output_re.match(line)
            if om:
                out_val = float(om.group(2))
                continue
            pm = peasants_re.match(line)
            if pm:
                peas_val = float(pm.group(1))
        rows.append(
            {
                "good_id": good_id,
                "output_modifier": float("nan") if out_val is None else out_val,
                "peasants_food": float("nan") if peas_val is None else peas_val,
            }
        )

    if not rows:
        return pd.DataFrame(columns=["output_modifier", "peasants_food"])

    df = pd.DataFrame(rows).set_index("good_id")[["output_modifier", "peasants_food"]]
    return df


def _build_inner_from_existing(
    old_inner: str,
    good_id: str,
    output_modifier: float | None,
    peasants_food: float | None,
) -> str:
    """Remove old output/peasants lines; append new ones after game_data (preserve other lines)."""
    lines = old_inner.split("\n")
    kept: list[str] = []
    for line in lines:
        if _OUTPUT_LINE_RE.match(line) or _PEASANTS_LINE_RE.match(line):
            continue
        kept.append(line)
    while kept and kept[-1].strip() == "":
        kept.pop()

    key = local_output_key(good_id)
    new_lines: list[str] = []
    if output_modifier is not None:
        new_lines.append(f"\t{key} = {_fmt_scalar(float(output_modifier))}")
    if peasants_food is not None:
        new_lines.append(f"\tlocal_peasants_food_consumption = {_fmt_scalar(float(peasants_food))}")

    if not kept:
        return "\n".join(new_lines) + ("\n" if new_lines else "")

    body = "\n".join(kept)
    if new_lines:
        if body.strip():
            return body + "\n" + "\n".join(new_lines) + "\n"
        return "\n".join(new_lines) + "\n"
    return body + ("\n" if body and not body.endswith("\n") else "")


def apply_pp_rgo_static_bonuses(path: Path | str, df: pd.DataFrame) -> None:
    """
    Update local_*_output_modifier and local_peasants_food_consumption lines inside each
    pp_rgo_bonus_* block. Preserves comments, block order, and non-numeric lines.

    df: index = good_id (as in pp_rgo_bonus_<id>), columns must include output_modifier
        and peasants_food (use NaN to omit a line).
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")

    required = {"output_modifier", "peasants_food"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame missing columns: {missing}")

    # Collect replacements using positions in the original text; apply from end to start
    # so indices stay valid.
    ops: list[tuple[int, int, str]] = []
    for good_id, row in df.iterrows():
        gid = str(good_id)
        pat = re.compile(rf"^pp_rgo_bonus_{re.escape(gid)}\s*=\s*\{{", re.MULTILINE)
        m = pat.search(text)
        if not m:
            raise ValueError(f"No block pp_rgo_bonus_{gid} in {path}")

        open_brace = m.end() - 1
        inner_t = _extract_inner_block(text, open_brace)
        if inner_t is None:
            raise ValueError(f"Unclosed block pp_rgo_bonus_{gid}")
        inner, close_after = inner_t
        close_brace_idx = close_after - 1

        out_v, peas_v = row["output_modifier"], row["peasants_food"]
        out_f: float | None = None if pd.isna(out_v) else float(out_v)
        peas_f: float | None = None if pd.isna(peas_v) else float(peas_v)

        new_inner = _build_inner_from_existing(inner, gid, out_f, peas_f)
        ops.append((open_brace, close_brace_idx, new_inner))

    for open_brace, close_brace_idx, new_inner in sorted(ops, key=lambda t: t[0], reverse=True):
        text = text[: open_brace + 1] + new_inner + text[close_brace_idx:]

    path.write_text(text, encoding="utf-8")
