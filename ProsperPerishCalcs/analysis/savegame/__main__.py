"""Terminal entry point for the savegame watcher. Run with: python -m analysis.savegame"""

from analysis.savegame import run_watcher


def main() -> None:
    run_watcher()


if __name__ == "__main__":
    main()
