"""Tests for the savegame processor module."""

from pathlib import Path

import pytest

from analysis.savegame.processor import (
    _content_hash,
    get_playthrough_id,
    get_playthrough_id_from_path,
    process_one_save,
    scan_for_work,
)


def test_get_playthrough_id_autosave_without_suffix():
    """autosave_{uuid}.eu5 (no _N) yields UUID with underscores."""
    p = Path("/x/autosave_7041fede-0316-4d09-8665-4bb89e1ad448.eu5")
    assert get_playthrough_id(p) == "7041fede_0316_4d09_8665_4bb89e1ad448"


def test_get_playthrough_id_autosave_with_number_suffix():
    """autosave_{uuid}_N.eu5 yields same UUID as unsuffixed."""
    p1 = Path("/x/autosave_7041fede-0316-4d09-8665-4bb89e1ad448.eu5")
    p2 = Path("/x/autosave_7041fede-0316-4d09-8665-4bb89e1ad448_99.eu5")
    id1 = get_playthrough_id(p1)
    id2 = get_playthrough_id(p2)
    assert id1 == id2 == "7041fede_0316_4d09_8665_4bb89e1ad448"


def test_get_playthrough_id_manual_save():
    """Manual save uses sanitized stem."""
    p = Path("/x/Campaign_England.eu5")
    assert get_playthrough_id(p) == "Campaign_England"


def test_get_playthrough_id_from_path_autosave():
    """get_playthrough_id_from_path works on path string (migration case)."""
    path_str = r"C:\Users\...\save games\autosave_7041fede-0316-4d09-8665-4bb89e1ad448_1.eu5"
    assert get_playthrough_id_from_path(path_str) == "7041fede_0316_4d09_8665_4bb89e1ad448"


def test_get_playthrough_id_from_path_manual():
    """get_playthrough_id_from_path for manual save."""
    path_str = r"/home/saves/Campaign_GB.eu5"
    assert get_playthrough_id_from_path(path_str) == "Campaign_GB"


def test_content_hash_deterministic(tmp_path: Path):
    """_content_hash is deterministic: same content + size => same hash."""
    f1 = tmp_path / "a.eu5"
    f1.write_bytes(b"x" * 100)
    h1, s1 = _content_hash(f1)
    h2, s2 = _content_hash(f1)
    assert h1 == h2
    assert s1 == s2 == 100


def test_content_hash_different_content(tmp_path: Path):
    """_content_hash differs when content or size differs."""
    f1 = tmp_path / "a.eu5"
    f2 = tmp_path / "b.eu5"
    f1.write_bytes(b"aaa")
    f2.write_bytes(b"bbb")
    h1, _ = _content_hash(f1)
    h2, _ = _content_hash(f2)
    assert h1 != h2


def test_content_hash_partial_only(tmp_path: Path):
    """_content_hash uses first 64KB + size (partial hash for speed)."""
    head = b"head"
    f1 = tmp_path / "a.eu5"
    f1.write_bytes(head + b"x" * 200)  # 204 bytes
    h1, s1 = _content_hash(f1)
    assert s1 == 204
    assert len(h1) == 64  # sha256 hex


def test_process_one_save_skips_by_sha256_when_path_differs(tmp_path: Path):
    """State with sha256 key causes skip even when path differs (simulates rename)."""
    import json

    save_path = tmp_path / "saves" / "autosave_7041fede-0316-4d09-8665-4bb89e1ad448_99.eu5"
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_bytes(b"save_content_123")

    play_dir = tmp_path / "out" / "7041fede_0316_4d09_8665_4bb89e1ad448"
    play_dir.mkdir(parents=True, exist_ok=True)

    content_hash, _ = _content_hash(save_path)
    pkl_name = "20250101_120000"
    (play_dir / f"{pkl_name}.pkl").write_bytes(b"pkl")
    state_path = play_dir / "processed.json"
    state_path.write_text(
        json.dumps({f"sha256:{content_hash}": {"pkl_name": pkl_name}}, indent=2),
        encoding="utf-8",
    )

    args = (str(save_path), str(play_dir), "{}", 1735732800, None)
    ok, name, result = process_one_save(args)

    assert ok
    assert result[0] == "skipped"
    assert result[1] == pkl_name
    assert result[2] == content_hash


def test_scan_for_work_excludes_by_sha256_orchestrator(tmp_path: Path):
    """Orchestrator (scan_for_work) skips files when sha256 in state — no dispatch."""
    import json

    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()
    save_path = saves_dir / "autosave_7041fede-0316-4d09-8665-4bb89e1ad448_99.eu5"
    save_path.write_bytes(b"save_content_xyz")

    playthrough_id = "7041fede_0316_4d09_8665_4bb89e1ad448"
    play_dir = tmp_path / "out" / playthrough_id
    play_dir.mkdir(parents=True)

    content_hash, _ = _content_hash(save_path)
    pkl_name = "20250101_120000"
    (play_dir / f"{pkl_name}.pkl").write_bytes(b"pkl")
    (play_dir / "processed.json").write_text(
        json.dumps({f"sha256:{content_hash}": {"pkl_name": pkl_name}}, indent=2),
        encoding="utf-8",
    )

    to_process = scan_for_work(
        saves_dir, tmp_path / "out", min_file_age_seconds=0
    )
    assert len(to_process) == 0
