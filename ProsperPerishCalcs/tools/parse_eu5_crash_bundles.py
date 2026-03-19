"""
Scan Paradox EU5 crash bundle folders: parse exception.txt, meta.yml, optional log tails.

Run from project root:
  uv run python tools/parse_eu5_crash_bundles.py
  uv run python tools/parse_eu5_crash_bundles.py --crashes-dir "C:/Users/.../Europa Universalis V/crashes"

Environment:
  EU5_CRASHES_DIR — default directory if --crashes-dir omitted.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


EXCEPTION_CODE_RE = re.compile(
    r"Unhandled Exception\s+(\S+)\s+\(([^)]+)\)\s+at address\s+(0x[0-9A-Fa-f]+)",
    re.I,
)
META_KEY_RE = re.compile(r"^([^#][^:]*):\s*(.*)$")


@dataclass
class BundleInfo:
    folder: str
    exception_code: str | None = None
    exception_name: str | None = None
    fault_address: str | None = None
    stack_fingerprint: str | None = None
    meta: dict[str, str] = field(default_factory=dict)
    mods: list[str] = field(default_factory=list)
    idlers: list[str] = field(default_factory=list)
    debug_tail: str | None = None
    error: str | None = None


def _parse_exception(path: Path) -> tuple[str | None, str | None, str | None, str | None]:
    text = path.read_text(encoding="utf-8", errors="replace")
    m = EXCEPTION_CODE_RE.search(text)
    if not m:
        return None, None, None, None
    code, name, addr = m.group(1), m.group(2), m.group(3)
    stack_lines: list[str] = []
    in_stack = False
    for line in text.splitlines():
        if line.strip().startswith("Stack Trace"):
            in_stack = True
            continue
        if in_stack and line.strip():
            stack_lines.append(line.strip())
    raw = "\n".join(stack_lines)
    fp = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return code, name, addr, fp


def _parse_meta(path: Path) -> tuple[dict[str, str], list[str], list[str]]:
    meta: dict[str, str] = {}
    mods: list[str] = []
    idlers: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = META_KEY_RE.match(line.strip())
        if not m:
            continue
        key, val = m.group(1).strip(), m.group(2).strip()
        if key.startswith("Mod_"):
            mods.append(f"{key}: {val}")
        elif key.startswith('"Idler') or key.startswith("Idler"):
            idlers.append(f"{key}: {val}")
        else:
            meta[key] = val
    return meta, mods, idlers


def _tail_file(path: Path, n: int) -> str | None:
    if not path.is_file():
        return None
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    if not lines:
        return None
    return "\n".join(lines[-n:])


def scan_crash_root(root: Path, tail_lines: int) -> list[BundleInfo]:
    results: list[BundleInfo] = []
    if not root.is_dir():
        return [
            BundleInfo(folder=str(root), error=f"not a directory: {root}")
        ]

    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        exc_path = child / "exception.txt"
        meta_path = child / "meta.yml"
        if not exc_path.is_file():
            continue

        info = BundleInfo(folder=child.name)
        try:
            code, name, addr, fp = _parse_exception(exc_path)
            info.exception_code = code
            info.exception_name = name
            info.fault_address = addr
            info.stack_fingerprint = fp
        except OSError as e:
            info.error = str(e)
            results.append(info)
            continue

        if meta_path.is_file():
            try:
                meta, mods, idlers = _parse_meta(meta_path)
                info.meta = meta
                info.mods = mods
                info.idlers = idlers
            except OSError as e:
                info.error = (info.error or "") + f" meta: {e}"

        dbg = child / "logs" / "debug.log"
        info.debug_tail = _tail_file(dbg, tail_lines)
        results.append(info)

    return results


def _print_table(
    bundles: list[BundleInfo],
    known_addresses: set[str],
) -> None:
    print("EU5 crash bundle summary\n")
    print(
        f"{'Folder':<42} {'Code':<12} {'Fault address':<20} {'Stack fp':<18} {'Known?':<6}"
    )
    print("-" * 102)
    for b in bundles:
        if b.error and not b.exception_code:
            print(f"{b.folder:<42} ERROR: {b.error}")
            continue
        known = ""
        if b.fault_address:
            la = b.fault_address.lower()
            known = "yes" if la in known_addresses else "no"
        print(
            f"{b.folder:<42} "
            f"{(b.exception_code or '-'):<12} "
            f"{(b.fault_address or '-'):<20} "
            f"{(b.stack_fingerprint or '-'):<18} "
            f"{known:<6}"
        )
    print()

    for b in bundles:
        if b.error:
            print(f"[{b.folder}] {b.error}\n")
        print(f"### {b.folder}")
        if b.exception_name:
            print(f"  Exception: {b.exception_name} ({b.exception_code})")
        if b.fault_address:
            print(f"  Fault address: {b.fault_address}")
        if b.stack_fingerprint:
            print(f"  Stack fingerprint (sha256[:16] of stack lines): {b.stack_fingerprint}")

        m = b.meta
        for key in (
            "AppVersion",
            "SCMCommit",
            "DateTime",
            "RenderAPI",
            "GPUName",
            "GPUDriverVersion",
        ):
            if key in m:
                print(f"  {key}: {m[key]}")
        if b.mods:
            print("  Mods:")
            for line in b.mods:
                print(f"    {line}")
        if b.idlers:
            print("  Idlers:")
            for line in b.idlers:
                print(f"    {line}")
        if b.debug_tail:
            print(f"  --- debug.log (last lines) ---")
            for line in b.debug_tail.splitlines():
                print(f"    {line}")
        print()


def main() -> int:
    default_root = os.environ.get("EU5_CRASHES_DIR")
    if not default_root:
        default_root = str(
            Path.home()
            / "Documents"
            / "Paradox Interactive"
            / "Europa Universalis V"
            / "crashes"
        )

    ap = argparse.ArgumentParser(description="Parse EU5 crash bundles under a crashes folder.")
    ap.add_argument(
        "--crashes-dir",
        type=Path,
        default=Path(default_root),
        help=f"Paradox crashes directory (default: {default_root})",
    )
    ap.add_argument(
        "--tail-lines",
        type=int,
        default=25,
        help="Lines to show from each bundle logs/debug.log (default: 25)",
    )
    ap.add_argument(
        "--known-address",
        action="append",
        default=[],
        metavar="0x...",
        help="Mark fault addresses as known (repeatable). Example: --known-address 0x00007FF70D541666",
    )
    args = ap.parse_args()

    known = {a.lower() for a in (args.known_address or [])}
    bundles = scan_crash_root(args.crashes_dir.resolve(), args.tail_lines)
    if not bundles:
        print(f"No crash bundles with exception.txt found under: {args.crashes_dir}", file=sys.stderr)
        return 1

    _print_table(bundles, known)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
