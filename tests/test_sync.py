import subprocess
from pathlib import Path

import pytest

from pd import capture, db, paths, sync


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    for d in paths.ProjectPaths(root).all_dirs():
        d.mkdir(parents=True)
    db.init_db(root)
    conn = db.connect(root / "pd.sqlite")
    yield root, conn
    conn.close()


@pytest.fixture
def source_video(tmp_path):
    video_path = tmp_path / "source.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=3:size=64x48:rate=10",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=3",
            "-shortest",
            str(video_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return video_path


def fake_vidclip(monkeypatch, calls: list):
    """vidclip isn't installed in this environment; stand in for it, capturing calls made."""
    original_run = subprocess.run

    def fake_run(cmd, **kwargs):
        if cmd[0] == "vidclip":
            calls.append(cmd)
            dest = Path(cmd[3])
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"fake video content")
            return subprocess.CompletedProcess(cmd, 0)
        return original_run(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", fake_run)


def test_sync_generates_files_for_current_clip(project, source_video, monkeypatch):
    root, conn = project
    project_paths = paths.ProjectPaths(root)
    scene_id, clip_id = capture.create_scene_and_clip(
        conn, project_paths, source_video, start_ts="0.2", end_ts="1.0", screenshot_ts="0.5"
    )
    conn.close()

    calls: list = []
    fake_vidclip(monkeypatch, calls)

    sync.run(root)

    screenshot_name = paths.screenshot_filename(scene_id, 1, clip_id)
    video_name = paths.video_filename(scene_id, 1, clip_id)
    assert (project_paths.screenshots / screenshot_name).is_file()
    assert (project_paths.video / video_name).is_file()
    assert len(calls) == 1
    assert calls[0][:2] == ["vidclip", "trim"]
    assert "--copy" in calls[0]


def test_sync_trashes_stale_files(project, source_video, monkeypatch):
    root, conn = project
    project_paths = paths.ProjectPaths(root)
    capture.create_scene_and_clip(
        conn, project_paths, source_video, start_ts="0.2", end_ts="1.0", screenshot_ts="0.5"
    )
    conn.close()

    stale_path = project_paths.screenshots / "STALE_001_abc1234.jpg"
    stale_path.write_bytes(b"stale")

    fake_vidclip(monkeypatch, [])
    sync.run(root)

    assert not stale_path.exists()
    assert (project_paths.trash_screenshots / "STALE_001_abc1234.jpg").is_file()


def test_sync_restores_screenshot_from_trash(project, source_video, monkeypatch):
    root, conn = project
    project_paths = paths.ProjectPaths(root)
    scene_id, clip_id = capture.create_scene_and_clip(
        conn, project_paths, source_video, start_ts="0.2", end_ts="1.0", screenshot_ts="0.5"
    )
    conn.close()

    screenshot_name = paths.screenshot_filename(scene_id, 1, clip_id)
    real_path = project_paths.screenshots / screenshot_name
    trashed_path = project_paths.trash_screenshots / screenshot_name
    real_path.rename(trashed_path)

    fake_vidclip(monkeypatch, [])
    sync.run(root)

    assert real_path.is_file()
    assert not trashed_path.exists()


def test_sync_skips_scenes_with_no_active_clip(project, source_video, monkeypatch):
    root, conn = project
    project_paths = paths.ProjectPaths(root)
    scene_id, clip_id = capture.create_scene_and_clip(
        conn, project_paths, source_video, start_ts="0.2", end_ts="1.0", screenshot_ts="0.5"
    )
    db.toggle_clip_active(conn, clip_id)  # now inactive, scene has no current clip
    conn.close()

    fake_vidclip(monkeypatch, [])
    sync.run(root)

    screenshot_name = paths.screenshot_filename(scene_id, 1, clip_id)
    assert not (project_paths.screenshots / screenshot_name).exists()
    assert (project_paths.trash_screenshots / screenshot_name).is_file()


def test_generate_video_includes_copy_for_mp4_source(tmp_path, monkeypatch):
    calls: list = []
    fake_vidclip(monkeypatch, calls)
    source = tmp_path / "source.mp4"
    dest = tmp_path / "out" / "clip.mp4"
    sync.generate_video(source, "0", "1", dest)
    assert "--copy" in calls[0]


def test_generate_video_omits_copy_for_non_mp4_source(tmp_path, monkeypatch):
    calls: list = []
    fake_vidclip(monkeypatch, calls)
    source = tmp_path / "source.avi"
    dest = tmp_path / "out" / "clip.mp4"
    sync.generate_video(source, "0", "1", dest)
    assert "--copy" not in calls[0]
