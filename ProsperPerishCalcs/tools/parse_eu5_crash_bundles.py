"""
Scan Paradox EU5 crash bundle folders: parse exception.txt, meta.yml, minidump.dmp, optional log tails.

Run from project root:
  uv run python tools/parse_eu5_crash_bundles.py
  uv run python tools/parse_eu5_crash_bundles.py --crashes-dir "C:/Users/.../Europa Universalis V/crashes"

When `minidump.dmp` is present, reads exception thread + RIP and (with --eu5-exe) disassembles the faulting
instruction (RVA into eu5.exe). Paradox names the dump `minidump.dmp` (not always `*.dmp` at bundle root).

Environment:
  EU5_CRASHES_DIR — default directory if --crashes-dir omitted.
  EU5_EXE — path to eu5.exe for disassembly (overridden by --eu5-exe).
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_64, Cs
from minidump.minidumpfile import MinidumpFile


EXCEPTION_CODE_RE = re.compile(
    r"Unhandled Exception\s+(\S+)\s+\(([^)]+)\)\s+at address\s+(0x[0-9A-Fa-f]+)",
    re.I,
)
META_KEY_RE = re.compile(r"^([^#][^:]*):\s*(.*)$")

# Loading eu5.exe with pefile is expensive; reuse one PE per path when disassembling multiple dumps.
_pefile_cache: dict[str, pefile.PE] = {}


def _get_pe_cached(exe: Path) -> pefile.PE:
    key = str(exe.resolve())
    if key not in _pefile_cache:
        pe = pefile.PE(key, fast_load=True)
        pe.parse_data_directories()
        _pefile_cache[key] = pe
    return _pefile_cache[key]


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
    # minidump.dmp (optional)
    minidump_error: str | None = None
    minidump_thread_id: str | None = None
    minidump_rip: str | None = None
    minidump_eu5_base: str | None = None
    minidump_rva: str | None = None
    minidump_disasm: str | None = None


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


def _eu5_image_base(mf: MinidumpFile) -> int | None:
    if mf.modules is None:
        return None
    for mod in mf.modules.modules:
        if not mod.name:
            continue
        if mod.name.lower().endswith("eu5.exe"):
            return mod.baseaddress
    return None


def _disassemble_at_rip(exe: Path, rip: int, eu5_base: int, lines: int = 12) -> str | None:
    """Map RIP to RVA, read bytes from on-disk eu5.exe, disassemble with Capstone."""
    rva = rip - eu5_base
    if rva < 0:
        return None
    pe = _get_pe_cached(exe)
    offset = pe.get_offset_from_rva(rva)
    if offset is None:
        for s in pe.sections:
            start = s.VirtualAddress
            end = start + max(s.Misc_VirtualSize, s.SizeOfRawData)
            if start <= rva < end:
                offset = s.PointerToRawData + (rva - start)
                break
    if offset is None:
        return None
    with exe.open("rb") as f:
        f.seek(offset)
        code = f.read(64)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    out: list[str] = []
    for i in md.disasm(code, rip):
        mark = "  << RIP" if i.address == rip else ""
        out.append(f"  0x{i.address:x}:  {i.mnemonic} {i.op_str}{mark}")
        if len(out) >= lines:
            break
    return "\n".join(out) if out else None


def _analyze_minidump(
    dmp_path: Path,
    eu5_exe: Path | None,
    do_disasm: bool,
) -> tuple[str | None, str | None, str | None, str | None, str | None, str | None]:
    """
    Returns: thread_id, rip, eu5_base, rva, disasm_block, error
    """
    mf: MinidumpFile | None = None
    try:
        mf = MinidumpFile.parse(str(dmp_path))
        if mf.exception is None or not mf.exception.exception_records:
            return None, None, None, None, None, "no exception stream in minidump"

        rec = mf.exception.exception_records[0]
        thread_id = f"0x{rec.ThreadId:08x}"
        er = rec.ExceptionRecord
        rip = er.ExceptionAddress

        base = _eu5_image_base(mf)
        if base is None:
            return thread_id, f"0x{rip:x}", None, None, None, "eu5.exe not in module list"

        rva = rip - base
        rva_s = f"0x{rva:x}"
        rip_s = f"0x{rip:x}"
        base_s = f"0x{base:x}"

        disasm = None
        if do_disasm and eu5_exe is not None and eu5_exe.is_file():
            disasm = _disassemble_at_rip(eu5_exe, rip, base)

        return thread_id, rip_s, base_s, rva_s, disasm, None
    except Exception as e:
        return None, None, None, None, None, str(e)
    finally:
        if mf is not None and getattr(mf, "file_handle", None):
            try:
                mf.file_handle.close()
            except OSError:
                pass


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


def scan_crash_root(
    root: Path,
    tail_lines: int,
    eu5_exe: Path | None,
    do_disasm: bool,
) -> list[BundleInfo]:
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

        dmp = child / "minidump.dmp"
        if dmp.is_file():
            tid, rip, base, rva, disasm, merr = _analyze_minidump(dmp, eu5_exe, do_disasm)
            info.minidump_thread_id = tid
            info.minidump_rip = rip
            info.minidump_eu5_base = base
            info.minidump_rva = rva
            info.minidump_disasm = disasm
            info.minidump_error = merr

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
        if b.minidump_thread_id or b.minidump_error:
            print("  --- minidump.dmp ---")
            if b.minidump_error:
                print(f"    error: {b.minidump_error}")
            if b.minidump_thread_id:
                print(f"    exception thread: {b.minidump_thread_id}")
            if b.minidump_rip:
                print(f"    RIP: {b.minidump_rip}")
            if b.minidump_eu5_base:
                print(f"    eu5.exe base (dump): {b.minidump_eu5_base}")
            if b.minidump_rva:
                print(f"    RVA in eu5.exe: {b.minidump_rva}")
            if b.minidump_disasm:
                print("    disassembly (Capstone):")
                for line in b.minidump_disasm.splitlines():
                    print(f"    {line}")
        print()


def main() -> int:
    # minidump library logs full tracebacks when PEB is missing from the dump (harmless for our use).
    logging.getLogger().setLevel(logging.CRITICAL)

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
    _candidates = [
        os.environ.get("EU5_EXE"),
        r"C:\Games\steamapps\common\Europa Universalis V\binaries\eu5.exe",
        r"C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis V\binaries\eu5.exe",
    ]
    default_exe: Path | None = None
    for c in _candidates:
        if c and Path(c).is_file():
            default_exe = Path(c)
            break
    ap.add_argument(
        "--eu5-exe",
        type=Path,
        default=default_exe,
        help="Path to eu5.exe (for RVA + disassembly from minidump.dmp). Default: EU5_EXE or first found install path.",
    )
    ap.add_argument(
        "--no-disasm",
        action="store_true",
        help="Parse minidump but skip Capstone disassembly.",
    )
    args = ap.parse_args()

    known = {a.lower() for a in (args.known_address or [])}
    eu5 = args.eu5_exe
    if eu5 is not None:
        eu5 = eu5.resolve()
    bundles = scan_crash_root(
        args.crashes_dir.resolve(),
        args.tail_lines,
        eu5,
        do_disasm=not args.no_disasm,
    )
    if not bundles:
        print(f"No crash bundles with exception.txt found under: {args.crashes_dir}", file=sys.stderr)
        return 1

    _print_table(bundles, known)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
