"""Convert Paradox mod text files to UTF-8 with BOM (CRLF line endings)."""

import codecs
from pathlib import Path


def convert_to_utf8_bom(directory: Path | str) -> None:
    """Convert .txt and .yml files in directory to UTF-8 BOM with CRLF."""
    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {dir_path}")

    extensions = (".txt", ".yml")

    for file_path in dir_path.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in extensions:
            try:
                content = file_path.read_bytes()

                if content.startswith(codecs.BOM_UTF8):
                    print(f"Skipping (already UTF-8 BOM): {file_path}")
                    continue

                try:
                    decoded_content = content.decode("utf-8")
                except UnicodeDecodeError:
                    decoded_content = content.decode("latin-1")

                normalized_content = decoded_content.replace("\r\n", "\n").replace("\r", "\n")
                file_path.write_text(normalized_content, encoding="utf-8-sig", newline="\r\n")
                print(f"Converted: {file_path}")
            except Exception as e:
                print(f"Failed to convert {file_path}: {e}")


if __name__ == "__main__":
    target_dir = Path(r"C:\Users\Anwender\Documents\Paradox Interactive\Europa Universalis V\mod")
    if target_dir.exists():
        convert_to_utf8_bom(target_dir)
        print("Conversion complete.")
    else:
        print(f"Directory not found: {target_dir}")
