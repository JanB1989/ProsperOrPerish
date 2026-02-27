"""Mod-asset fix scripts for Paradox EU5 modding."""

from pathlib import Path

from tools.convert_utf8_bom import convert_to_utf8_bom
from tools.fix_dds_mipmaps import fix_dds_mipmaps, _find_texconv


def run_all_fixes(
    mod_path: Path | str,
    texconv_path: Path | str | None = None,
    skip_utf8_bom: bool = False,
    skip_dds_mipmaps: bool = False,
) -> None:
    """Run all mod-asset fix scripts. Only touches files in mod_path, never the game install."""
    mod = Path(mod_path)

    if not skip_utf8_bom:
        print("--- UTF-8 BOM conversion ---")
        convert_to_utf8_bom(mod)
        print()

    if not skip_dds_mipmaps:
        print("--- DDS mipmap fix ---")
        if _find_texconv(texconv_path) is None:
            print("Warning: texconv not found. Skip DDS mipmap fix. Install DirectXTex or add texconv to PATH.")
        else:
            fix_dds_mipmaps(mod, texconv_path)
        print()

    print("All fixes complete.")
