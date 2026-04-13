# ProsperPerishCalcs
Professional analysis suite for Europa Universalis V modding.

## Structure
- `docs/`: EU5 crash investigation workflow and Paradox escalation checklists (`eu5_pp_crash_investigation.md`, `paradox_escalation_checklist.md`).
- `tools/`: Mod-asset fix scripts (UTF-8 BOM conversion, DDS mipmaps), plus `parse_eu5_crash_bundles.py` to summarize crash folders (`exception.txt`, `meta.yml`, **`minidump.dmp`** RVA + Capstone disassembly vs `eu5.exe`, `debug.log` tail). Run via `uv run python main.py` or `uv run python tools/parse_eu5_crash_bundles.py`.
- `core/parser/`: Robust Paradox script parsing engine.
- `core/data/`: Live data modules for Goods, Buildings, Locations, Defines, and Pops.
- `analysis/building_levels/`: Building capacity and economic analysis tools.
- `analysis/building_levels/notebooks/`: Jupyter notebooks (`building_pm_io_matrix.ipynb` merged mod+game; `building_pm_io_matrix_vanilla.ipynb` vanilla-only).
- `analysis/building_levels/scripts/`: Command-line analysis tools.

## Paradox Script Syntax
The parser handles EUV-specific modding prefixes:
- `INJECT` / `TRY_INJECT`: Merges modded properties into vanilla definitions (Additive).
- `REPLACE` / `TRY_REPLACE`: Completely overwrites vanilla definitions (Destructive).
- Mirrored paths: Mod files automatically override vanilla files at the same relative path.
- Folder logic: The folder structure is identical between vanilla and mod, but `.txt` files within those folders can have different names. The parser iterates through all files in the mirrored directory to construct the final state.

## Usage
All data is fetched live from the game and mod directories configured in `analysis/building_levels/config.json`.

### Imports and Running Code
- Run all commands from the **project root**.
- Use `uv run` for scripts, tests, and Jupyter.
- After `uv sync`, `core` and `analysis` are importable; no `sys.path` changes required.
- Start notebooks: `uv run jupyter notebook` (or `uv run python -m jupyter notebook`).
- Paths (game, mod, data) are configured in `analysis/building_levels/config.json`.

### Mod Fix Scripts
Run all fixes (UTF-8 BOM for Paradox scripts, DDS mipmaps for textures) on the mod configured in `config.json`:
```
uv run python main.py
```
Requires [DirectXTex](https://github.com/microsoft/DirectXTex/releases) `texconv` on PATH for DDS mipmap generation.

### Environment Management (uv)
This project uses `uv` for dependency management. Always use `uv run` to execute scripts or tests to ensure the correct virtual environment is used:
- **Run Tests**: `uv run pytest`
- **Run Scripts**: `uv run python path/to/script.py`
- **Update Dependencies**: `uv sync`
