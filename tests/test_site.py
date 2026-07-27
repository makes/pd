import subprocess

import pytest
from PIL import Image

from pd import capture, db, paths, site


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
            "testsrc=duration=3:size=640x480:rate=10",
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


def test_sync_thumbnails_generates_and_prunes(project, source_video):
    root, conn = project
    project_paths = paths.ProjectPaths(root)
    capture.create_scene_and_clip(
        conn, project_paths, source_video, start_ts="0.2", end_ts="1.0", screenshot_ts="0.5"
    )
    conn.close()

    stale_thumb = project_paths.thumbnails / "orphan.jpg"
    stale_thumb.parent.mkdir(parents=True, exist_ok=True)
    stale_thumb.write_bytes(b"stale")

    site.sync_thumbnails(project_paths)

    screenshot_files = list(project_paths.screenshots.iterdir())
    assert len(screenshot_files) == 1
    thumb_path = project_paths.thumbnails / screenshot_files[0].name
    assert thumb_path.is_file()
    with Image.open(thumb_path) as img:
        assert max(img.size) <= 320
    assert not stale_thumb.exists()


def test_site_generates_category_page_and_index(project, source_video):
    root, conn = project
    project_paths = paths.ProjectPaths(root)
    scene_id, clip_id = capture.create_scene_and_clip(
        conn, project_paths, source_video, start_ts="0.2", end_ts="1.0", screenshot_ts="0.5"
    )
    db.update_scene_field(conn, scene_id, "title", "My Scene")
    db.set_scene_links(conn, scene_id, ["http://example.com"])
    conn.close()

    site.run(root)

    category_page = project_paths.content / "C.html"
    index_page = project_paths.content / "index.html"
    assert category_page.is_file()
    assert index_page.is_file()

    text = category_page.read_text(encoding="utf-8")
    assert "My Scene" in text
    assert clip_id in text
    assert "source.mp4" in text
    assert "http://example.com" in text
    assert 'href="video/' in text
    assert 'href="image/screenshots/' in text
    assert 'src="thumbnails/' in text

    index_text = index_page.read_text(encoding="utf-8")
    assert 'href="C.html"' in index_text


def test_site_excludes_scenes_without_active_clip(project, source_video):
    root, conn = project
    project_paths = paths.ProjectPaths(root)
    scene_id, clip_id = capture.create_scene_and_clip(
        conn, project_paths, source_video, start_ts="0.2", end_ts="1.0", screenshot_ts="0.5"
    )
    db.toggle_clip_active(conn, clip_id)
    conn.close()

    site.run(root)

    text = (project_paths.content / "C.html").read_text(encoding="utf-8")
    assert clip_id not in text


def test_site_category_filter_only_writes_that_page(project, source_video):
    root, conn = project
    project_paths = paths.ProjectPaths(root)
    capture.create_scene_and_clip(
        conn, project_paths, source_video, start_ts="0.2", end_ts="1.0", screenshot_ts="0.5"
    )
    conn.close()

    site.run(root, category="C")

    assert (project_paths.content / "C.html").is_file()
    assert (project_paths.content / "index.html").is_file()
