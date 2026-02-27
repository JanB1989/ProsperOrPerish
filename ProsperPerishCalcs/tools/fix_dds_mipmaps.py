"""Add mipmaps to DDS texture files using texconv (DirectXTex)."""

import shutil
import subprocess
import urllib.request
from pathlib import Path

# Prebuilt texconv from DirectXTex releases (jul2025)
TEXCONV_URL = "https://github.com/microsoft/DirectXTex/releases/download/jul2025/texconv.exe"


def _get_texconv_cache_dir() -> Path:
    """Project-local cache for downloaded texconv."""
    return Path(__file__).resolve().parent.parent / ".tools"


def _download_texconv() -> Path | None:
    """Download texconv.exe to project cache. Returns path if successful."""
    cache_dir = _get_texconv_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / "texconv.exe"

    if dest.exists():
        return dest

    try:
        print("Downloading texconv.exe from DirectXTex...")
        urllib.request.urlretrieve(TEXCONV_URL, dest)
        print(f"Downloaded to {dest}")
        return dest
    except OSError as e:
        print(f"Failed to download texconv: {e}")
        if dest.exists():
            dest.unlink()
        return None


def _find_texconv(texconv_path: Path | str | None) -> Path | None:
    """Locate texconv executable. Returns None if not found."""
    if texconv_path is not None:
        p = Path(texconv_path)
        if p.is_file():
            return p
        if shutil.which(str(p)):
            return p

    # Try PATH
    found = shutil.which("texconv")
    if found:
        return Path(found)

    # Common DirectXTex install locations
    common_paths = [
        Path.home() / "DirectXTex" / "bin" / "texconv.exe",
        Path.home() / "DirectXTex" / "Texconv" / "Release" / "texconv.exe",
        Path("C:/DirectXTex/bin/texconv.exe"),
        Path("C:/Program Files/DirectXTex/texconv.exe"),
    ]
    for p in common_paths:
        if p.exists():
            return p

    # Auto-download prebuilt binary
    return _download_texconv()


def fix_dds_mipmaps(directory: Path | str, texconv_path: Path | str | None = None) -> None:
    """Add mipmaps to all DDS files in directory using texconv."""
    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {dir_path}")

    texconv = _find_texconv(texconv_path)
    if texconv is None:
        print("Warning: texconv not found. Skip DDS mipmap fix. Install DirectXTex or add texconv to PATH.")
        return

    dds_files = list(dir_path.rglob("*.dds"))
    if not dds_files:
        print(f"No DDS files found in {dir_path}")
        return

    for file_path in dds_files:
        try:
            subprocess.run(
                [str(texconv), "-y", "-nologo", str(file_path)],
                check=True,
                capture_output=True,
            )
            print(f"Fixed mipmaps: {file_path}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to fix {file_path}: {e}")
        except OSError as e:
            print(f"Error running texconv on {file_path}: {e}")
