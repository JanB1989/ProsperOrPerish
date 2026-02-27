"""Main entry point for ProsperPerishCalcs."""

import json
from pathlib import Path

from tools import run_all_fixes


def main():
    config_path = Path(__file__).parent / "analysis" / "building_levels" / "config.json"
    if config_path.exists():
        with open(config_path) as f:
            cfg = json.load(f)
        mod_path = Path(cfg["mod_path"])
        game_path = Path(cfg["game_path"])
    else:
        mod_path = Path(
            r"C:\Users\Anwender\Documents\Paradox Interactive\Europa Universalis V\mod\Prosper or Perish (Population Growth & Food Rework)"
        )
        game_path = Path(r"C:\Games\steamapps\common\Europa Universalis V\game")

    run_all_fixes(mod_path=mod_path)


if __name__ == "__main__":
    main()
