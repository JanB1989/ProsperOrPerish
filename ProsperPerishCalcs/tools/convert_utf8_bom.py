"""Convert Paradox mod text files to UTF-8 with BOM (CRLF line endings)."""

import argparse
import codecs
from pathlib import Path

DEFAULT_MOD_ROOT = Path(
    r"C:\Users\Anwender\Documents\Paradox Interactive\Europa Universalis V\mod"
)
DEFAULT_EXTENSIONS = (".txt", ".yml")


def convert_to_utf8_bom(
    directory: Path | str,
    *,
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS,
) -> dict[str, int]:
    """Convert matching files under ``directory`` (recursive) to UTF-8 BOM with CRLF.

    Returns counts: converted, skipped_bom, failed.
    """
    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {dir_path}")

    ext_set = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions}
    stats = {"converted": 0, "skipped_bom": 0, "failed": 0}

    for file_path in sorted(dir_path.rglob("*")):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in ext_set:
            continue
        try:
            content = file_path.read_bytes()

            if content.startswith(codecs.BOM_UTF8):
                print(f"Skipping (already UTF-8 BOM): {file_path}")
                stats["skipped_bom"] += 1
                continue

            try:
                decoded_content = content.decode("utf-8")
            except UnicodeDecodeError:
                decoded_content = content.decode("latin-1")

            normalized_content = decoded_content.replace("\r\n", "\n").replace("\r", "\n")
            file_path.write_text(normalized_content, encoding="utf-8-sig", newline="\r\n")
            print(f"Converted: {file_path}")
            stats["converted"] += 1
        except Exception as e:
            print(f"Failed to convert {file_path}: {e}")
            stats["failed"] += 1

    return stats


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Recursively convert .txt/.yml under the EU5 mod folder to UTF-8 BOM with CRLF."
    )
    p.add_argument(
        "mod_root",
        nargs="?",
        type=Path,
        default=DEFAULT_MOD_ROOT,
        help=f"Path to the mod directory (default: {DEFAULT_MOD_ROOT})",
    )
    p.add_argument(
        "--extra-ext",
        action="append",
        default=[],
        metavar="EXT",
        help="Additional extension to include (e.g. --extra-ext .yaml). May be repeated.",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    exts = tuple(DEFAULT_EXTENSIONS) + tuple(
        e if e.startswith(".") else f".{e}" for e in args.extra_ext
    )
    target = args.mod_root
    if not target.exists():
        print(f"Directory not found: {target}")
        raise SystemExit(1)
    print(f"Scanning (recursive): {target.resolve()}")
    print(f"Extensions: {', '.join(sorted(set(exts)))}")
    out = convert_to_utf8_bom(target, extensions=exts)
    print(
        "Done — "
        f"converted: {out['converted']}, "
        f"skipped (already BOM): {out['skipped_bom']}, "
        f"failed: {out['failed']}"
    )
