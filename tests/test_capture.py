import subprocess

import pytest
from PIL import Image

from pd import capture, db, paths


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


def test_create_scene_and_clip(project, source_video):
    root, conn = project
    project_paths = paths.ProjectPaths(root)

    scene_id, clip_id = capture.create_scene_and_clip(
        conn, project_paths, source_video, start_ts="0.5", end_ts="2.0", screenshot_ts="1.0"
    )

    scene_row = conn.execute("SELECT * FROM scene WHERE scene_id = ?", (scene_id,)).fetchone()
    assert scene_row is not None
    assert scene_row["category"] == "C"

    clip_row = conn.execute("SELECT * FROM clip WHERE clip_id = ?", (clip_id,)).fetchone()
    assert clip_row is not None
    assert clip_row["scene_id"] == scene_id
    assert clip_row["start_ts"] == "0.5"
    assert clip_row["end_ts"] == "2.0"
    assert clip_row["screenshot_ts"] == "1.0"
    assert clip_row["source_filename"] == source_video.name
    assert clip_row["source_dir"] == str(source_video.parent)
    assert clip_row["active"] == 1
    assert clip_row["source_size"] == source_video.stat().st_size

    screenshot_path = project_paths.screenshots / paths.screenshot_filename(scene_id, 1, clip_id)
    assert screenshot_path.is_file()
    with Image.open(screenshot_path) as img:
        assert img.size == (64, 48)
