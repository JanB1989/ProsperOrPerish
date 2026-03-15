"""Process EU5 savegames to .pkl files. Matches savegame_to_pandas.ipynb output format."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path

from analysis.building_levels.building_analysis.utils import load_config

LOG = logging.getLogger(__name__)
MAX_WORKERS = 8
STATE_FILENAME = "processed.json"
DEFAULT_PKL_BASE = Path(__file__).resolve().parent / "notebooks" / "save_game_temp"

# EU5 autosave: autosave_{uuid}.eu5 or autosave_{uuid}_N.eu5 — (?:_\d+)? makes _N optional
_AUTOSAVE_RE = re.compile(r"autosave_([a-f0-9-]+)(?:_\d+)?\.eu5$", re.I)


def get_pkl_dir(base: Path) -> Path:
    """Resolve to playthrough subfolder (newest by pkl stem) or base if flat layout."""
    if not base.exists():
        return base
    subdirs = [d for d in base.iterdir() if d.is_dir()]
    pkl_subdirs = [d for d in subdirs if list(d.glob("*.pkl"))]
    if pkl_subdirs:
        return max(
            pkl_subdirs,
            key=lambda d: max((f.stem for f in d.glob("*.pkl")), default=""),
        )
    return base


def resolve_pkl_dir(user_path: str | Path | None = None) -> Path:
    """Use user path if provided and exists, else newest playthrough in default base."""
    if user_path is not None:
        p = Path(user_path).resolve()
        if p.exists():
            return p
    return get_pkl_dir(DEFAULT_PKL_BASE)


def get_playthrough_id(path: Path) -> str:
    """Extract playthrough ID from save path. Autosave UUID or sanitized stem for manual saves."""
    m = _AUTOSAVE_RE.match(path.name)
    if m:
        return m.group(1).replace("-", "_")
    stem = re.sub(r"[^a-zA-Z0-9]+", "_", path.stem).strip("_")
    if stem:
        return stem
    try:
        mtime = int(path.stat().st_mtime)
        return f"unknown_{mtime}"
    except OSError:
        return "unknown"


def get_playthrough_id_from_path(path_str: str) -> str:
    """Like get_playthrough_id but from path string only (for migration, no file access)."""
    name = Path(path_str).name
    m = _AUTOSAVE_RE.match(name)
    if m:
        return m.group(1).replace("-", "_")
    stem = Path(path_str).stem
    stem = re.sub(r"[^a-zA-Z0-9]+", "_", stem).strip("_")
    return stem if stem else "unknown"


def _parse_ingame_date(s: str | None) -> str:
    """Parse Paradox date string to sortable format. '1346.3.1' -> '1346_03_01'."""
    s = str(s or "1337.1.1")
    parts = s.split(".")
    y = int(parts[0]) if parts else 1337
    m = int(parts[1]) if len(parts) > 1 else 1
    d = int(parts[2]) if len(parts) > 2 else 1
    return f"{y}_{m:02d}_{d:02d}"


def get_ingame_date_from_save(save) -> str:
    """Extract in-game date from save and return sortable string (YYYY_MM_DD)."""
    gd = getattr(save, "game_date", None)
    if gd is not None and hasattr(gd, "year") and hasattr(gd, "month") and hasattr(gd, "day"):
        return f"{gd.year}_{gd.month:02d}_{gd.day:02d}"
    data = getattr(save, "_data", None) or {}
    meta = data.get("metadata") if isinstance(data, dict) else {}
    if not isinstance(meta, dict):
        meta = {}
    date_val = meta.get("date")
    return _parse_ingame_date(date_val)


def _mtime_to_pkl_stem(mtime: int) -> str:
    """Format file mtime as human-readable pkl stem. YYYYMMDD_HHMMSS."""
    return datetime.fromtimestamp(mtime).strftime("%Y%m%d_%H%M%S")


def _state_key(path: Path, mtime: int, size: int) -> str:
    """Unique key for state file. Use resolved path for consistency."""
    return f"{path.resolve()}|{mtime}|{size}"


def _content_hash(path: Path) -> tuple[str, int]:
    """Fast content hash for deduplication. Hashes first 64KB + file size only.

    Avoids reading hundreds of MB; check completes in milliseconds per file.
    Returns (hex_hash, size).
    """
    size = path.stat().st_size
    sample_size = 64 * 1024  # 64 KB
    with open(path, "rb") as f:
        head = f.read(sample_size)
    h = hashlib.sha256(head + str(size).encode())
    return h.hexdigest(), size


def _find_state_match(
    state: dict, path: Path, mtime: int, size: int, play_dir: Path
) -> bool:
    """Return True if we've already processed this save (path-based or content-hash).
    Path-based first (no read). Content-hash when path fails (handles renames).
    """
    key = _state_key(path, mtime, size)
    if key in state:
        pkl_name = state[key].get("pkl_name", "")
        if pkl_name and (play_dir / f"{pkl_name}.pkl").exists():
            return True
    path_resolved = path.resolve()
    for state_key, entry in state.items():
        parts = state_key.split("|")
        if len(parts) != 3:
            continue
        stored_path, _, stored_size = parts
        try:
            if Path(stored_path).resolve() == path_resolved and int(stored_size) == size:
                pkl_name = entry.get("pkl_name", "")
                if pkl_name and (play_dir / f"{pkl_name}.pkl").exists():
                    return True
        except (ValueError, OSError):
            continue
    # Path-based failed; check content hash (handles EU5 autosave renames)
    try:
        content_hash, _ = _content_hash(path)
        sha256_key = f"sha256:{content_hash}"
        if sha256_key in state:
            pkl_name = state[sha256_key].get("pkl_name", "")
            if pkl_name and (play_dir / f"{pkl_name}.pkl").exists():
                return True
    except OSError:
        pass
    return False


def _load_state(state_path: Path) -> dict:
    """Load processed.json state. Returns {state_key: {"pkl_name": "20260311_172007"}}."""
    if not state_path.exists():
        return {}
    try:
        with open(state_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state_path: Path, state: dict) -> None:
    """Write state to processed.json."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def process_one_save(args: tuple[str, str, str, int, int | None]) -> tuple[bool, str, str | tuple[str, str, str]]:
    """Load save, build datalocations, write to {timestamp}.pkl. Top-level for ProcessPoolExecutor.

    Returns (ok, path_name, result). result is ("created"|"skipped"|"deferred", pkl_stem, content_hash) on success,
    else error str.
    Content-hash check runs first (partial hash, fast) to skip already-processed renamed files.
    """
    path_str, play_dir_str, config_str, mtime, size_arg = args
    from pathlib import Path

    from analysis.savegame.datalocations import create_datalocations_pkl_from_save
    from analysis.savegame.loader import load_save

    path = Path(path_str)
    play_dir = Path(play_dir_str)
    try:
        config = json.loads(config_str)
    except json.JSONDecodeError:
        config = {}
    max_retries = int(config.get("savegame_read_retries", 3))
    retry_delay = float(config.get("savegame_retry_delay_seconds", 3.0))

    # Stability check: re-stat before read; if file changed, defer to next cycle
    if size_arg is not None:
        try:
            stat = path.stat()
            if int(stat.st_mtime) != mtime or stat.st_size != size_arg:
                return (True, path.name, ("deferred", "", ""))
        except OSError:
            return (True, path.name, ("deferred", "", ""))

    last_error: BaseException | None = None
    for attempt in range(max_retries):
        try:
            content_hash, size = _content_hash(path)
            sha256_key = f"sha256:{content_hash}"

            state = _load_state(play_dir / STATE_FILENAME)

            if sha256_key in state:
                pkl_name = state[sha256_key].get("pkl_name", "")
                if pkl_name and (play_dir / f"{pkl_name}.pkl").exists():
                    return (True, path.name, ("skipped", pkl_name, content_hash))

            key = _state_key(path, mtime, size)
            if key in state:
                pkl_name = state[key].get("pkl_name", "")
                if pkl_name and (play_dir / f"{pkl_name}.pkl").exists():
                    return (True, path.name, ("skipped", pkl_name, content_hash))

            pkl_stem = _mtime_to_pkl_stem(mtime)
            out_path = play_dir / f"{pkl_stem}.pkl"
            if out_path.exists():
                return (True, path.name, ("skipped", pkl_stem, content_hash))

            save = load_save(path=path_str)
            path_resolver = None
            if config:
                from core.parser.path_resolver import PathResolver

                path_resolver = PathResolver(
                    config.get("game_path", ""), config.get("mod_path", "")
                )
            create_datalocations_pkl_from_save(save, out_path, path_resolver=path_resolver)
            return (True, path.name, ("created", pkl_stem, content_hash))
        except (OSError, PermissionError, subprocess.CalledProcessError) as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                LOG.debug("%s read attempt %s failed, retrying: %s", path.name, attempt + 1, e)
                continue
            return (False, path.name, str(e))
    return (False, path.name, str(last_error or RuntimeError("max retries exceeded")))


def get_all_save_paths(save_games_dir: str | Path) -> list[Path]:
    """Return paths to all .eu5 saves, newest first by mtime."""
    path = Path(save_games_dir)
    if not path.is_dir():
        return []
    all_saves = list(path.glob("*.eu5"))
    return sorted(
        (p.resolve() for p in all_saves),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def scan_for_work(
    save_games_dir: Path,
    output_dir: Path,
    min_file_age_seconds: float = 10.0,
) -> list[tuple[Path, int, int, Path]]:
    """Return list of (path, mtime, size, play_dir) for saves needing work.

    Skips if (path, mtime, size) in playthrough state and pkl exists.
    Skips files younger than min_file_age_seconds (avoids reading while game is writing).
    Uses lazy state loading per playthrough.
    """
    all_saves = get_all_save_paths(save_games_dir)
    state_cache: dict[str, dict] = {}
    to_process: list[tuple[Path, int, int, Path]] = []
    now = time.time()

    for p in all_saves:
        try:
            stat = p.stat()
            mtime, size = int(stat.st_mtime), stat.st_size
            if (now - mtime) < min_file_age_seconds:
                continue
            playthrough_id = get_playthrough_id(p)
            play_dir = output_dir / playthrough_id

            if playthrough_id not in state_cache:
                state_cache[playthrough_id] = _load_state(play_dir / STATE_FILENAME)
            state = state_cache[playthrough_id]

            if _find_state_match(state, p, mtime, size, play_dir):
                continue
            to_process.append((p, mtime, size, play_dir))
        except OSError:
            continue

    return to_process


def migrate_flat_to_subfolders(base: Path) -> bool:
    """If base has flat *.pkl and processed.json, move them into playthrough subfolders.
    Returns True if migration ran.
    """
    state_path = base / STATE_FILENAME
    if not state_path.exists():
        return False
    flat_pkls = list(base.glob("*.pkl"))
    if not flat_pkls:
        return False
    # Check for existing playthrough subdirs with pkls — if so, already migrated.
    # Exclude backup/ etc. which may contain pkls but are not our structure.
    subdirs = [d for d in base.iterdir() if d.is_dir() and d.name.lower() not in ("backup",)]
    for d in subdirs:
        if list(d.glob("*.pkl")):
            return False  # Already has subfolder structure
    try:
        state = _load_state(state_path)
    except Exception:
        return False
    if not state:
        return False

    # Group pkl_name by playthrough_id (skip sha256 keys — no path to infer playthrough)
    by_playthrough: dict[str, list[tuple[str, str]]] = {}
    for state_key, entry in state.items():
        parts = state_key.split("|")
        if len(parts) != 3:
            continue
        pkl_name = entry.get("pkl_name")
        if not pkl_name:
            continue
        path_part = parts[0]
        playthrough_id = get_playthrough_id_from_path(path_part)
        by_playthrough.setdefault(playthrough_id, []).append((state_key, pkl_name))

    if not by_playthrough:
        return False  # State format incompatible (no pkl_name); skip migration

    for playthrough_id, items in by_playthrough.items():
        play_dir = base / playthrough_id
        play_dir.mkdir(parents=True, exist_ok=True)
        play_state = {}
        for state_key, pkl_name in items:
            src = base / f"{pkl_name}.pkl"
            if src.exists():
                dst = play_dir / f"{pkl_name}.pkl"
                src.rename(dst)
            play_state[state_key] = {"pkl_name": pkl_name}
        _save_state(play_dir / STATE_FILENAME, play_state)

    state_path.unlink()
    LOG.info("Migrated %s pkls into %s playthrough folders.", len(flat_pkls), len(by_playthrough))
    return True


def run_watcher(
    save_games_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    scan_interval: float = 20.0,
    max_workers: int = MAX_WORKERS,
    min_file_age_seconds: float = 10.0,
) -> None:
    """Watch save folder, create .pkl for each new save. Output: {YYYYMMDD_HHMMSS}.pkl from save mtime."""
    config = load_config()
    save_games_dir = Path(
        save_games_dir or config.get("save_games_dir") or ""
    )
    if not save_games_dir or not save_games_dir.is_dir():
        raise ValueError(
            f"save_games_dir must be a valid directory. Got: {save_games_dir}"
        )

    if output_dir is None:
        output_dir = Path(__file__).resolve().parent / "notebooks" / "save_game_temp"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    min_file_age_seconds = float(
        config.get("savegame_min_file_age_seconds", min_file_age_seconds)
    )

    migrate_flat_to_subfolders(output_dir)

    debug_log = output_dir / "watcher_debug.log"
    file_handler = logging.FileHandler(debug_log, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.INFO)
    stderr_handler.setFormatter(logging.Formatter("%(message)s"))

    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[stderr_handler, file_handler],
        force=True,
    )
    LOG.info("Processor starting: %s -> %s", save_games_dir, output_dir)
    LOG.info("Workers: %s", max_workers)

    config_dict = {k: str(v) for k, v in config.items()}
    config_str = json.dumps(config_dict)

    while True:
        to_process = scan_for_work(
            save_games_dir, output_dir, min_file_age_seconds=min_file_age_seconds
        )
        n_saves = len(get_all_save_paths(save_games_dir))
        n_skip = n_saves - len(to_process)

        if not to_process:
            LOG.info(
                "%s saves, %s already done, nothing to process (sleeping %ss)",
                n_saves, n_skip, scan_interval,
            )
            time.sleep(scan_interval)
            continue

        LOG.info(
            "%s saves, %s already done, processing %s in parallel (workers=%s)",
            n_saves, n_skip, len(to_process), max_workers,
        )

        args_list = [
            (str(p), str(play_dir), config_str, mtime, size)
            for p, mtime, size, play_dir in to_process
        ]

        with ProcessPoolExecutor(max_workers=max_workers) as ex:
            results = list(zip(to_process, ex.map(process_one_save, args_list)))

        # Group state updates by play_dir to avoid races
        updates_by_dir: dict[Path, dict[str, dict]] = {}
        for (path, mtime, size, play_dir), (ok, name, result) in results:
            if ok:
                action, pkl_stem, content_hash = result
                if action == "deferred":
                    LOG.debug("%s -> deferred (file changed during scan)", name)
                    continue
                key = _state_key(path, mtime, size)
                updates_by_dir.setdefault(play_dir, {})
                updates_by_dir[play_dir][key] = {"pkl_name": pkl_stem}
                updates_by_dir[play_dir][f"sha256:{content_hash}"] = {"pkl_name": pkl_stem}
                if action == "skipped":
                    LOG.info("%s -> skipped (pkl exists)", name)
                else:
                    LOG.info("%s -> %s.pkl", name, pkl_stem)
            else:
                LOG.error("%s -> failed: %s", name, result)

        for play_dir, new_entries in updates_by_dir.items():
            state_path = play_dir / STATE_FILENAME
            state = _load_state(state_path)
            state.update(new_entries)
            _save_state(state_path, state)

        time.sleep(scan_interval)
