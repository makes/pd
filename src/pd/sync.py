import shutil
import sqlite3
import subprocess
from pathlib import Path

from . import capture, db, paths

MP4_SAFE_EXTENSIONS = {".mp4", ".m4v", ".mov"}


def run(root: Path) -> None:
    project_paths = paths.ProjectPaths(root)
    conn = db.connect(project_paths.db)
    try:
        keep_screenshots: set[str] = set()
        keep_videos: set[str] = set()

        for scene in db.list_scenes(conn):
            scene_id = scene["scene_id"]
            current_clip = db.get_latest_active_clip(conn, scene_id)
            if current_clip is None:
                continue

            seq = db.clip_seq(conn, scene_id, current_clip["clip_id"])
            screenshot_name = paths.screenshot_filename(scene_id, seq, current_clip["clip_id"])
            video_name = paths.video_filename(scene_id, seq, current_clip["clip_id"])
            keep_screenshots.add(screenshot_name)
            keep_videos.add(video_name)

            _ensure_screenshot(project_paths, current_clip, screenshot_name)
            _ensure_video(project_paths, current_clip, video_name)

        _trash_stale(project_paths.screenshots, project_paths.trash_screenshots, keep_screenshots)
        _trash_stale(project_paths.video, project_paths.trash_video, keep_videos)
    finally:
        conn.close()


def _ensure_screenshot(project_paths: paths.ProjectPaths, clip_row: sqlite3.Row, filename: str) -> None:
    dest = project_paths.screenshots / filename
    if dest.exists():
        return
    trashed = project_paths.trash_screenshots / filename
    if trashed.exists():
        shutil.move(str(trashed), str(dest))
        return
    source_path = paths.clip_source_path(clip_row)
    capture.generate_screenshot(source_path, clip_row["screenshot_ts"], dest)


def _ensure_video(project_paths: paths.ProjectPaths, clip_row: sqlite3.Row, filename: str) -> None:
    dest = project_paths.video / filename
    if dest.exists():
        return
    trashed = project_paths.trash_video / filename
    if trashed.exists():
        shutil.move(str(trashed), str(dest))
        return
    source_path = paths.clip_source_path(clip_row)
    generate_video(source_path, clip_row["start_ts"], clip_row["end_ts"], dest)


def generate_video(source_path: Path, start_ts: str, end_ts: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["vidclip", "trim", str(source_path), str(dest), "--start", start_ts, "--end", end_ts]
    if source_path.suffix.lower() in MP4_SAFE_EXTENSIONS:
        cmd.append("--copy")
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _trash_stale(source_dir: Path, trash_dir: Path, keep_names: set[str]) -> None:
    for path in source_dir.iterdir():
        if path.is_file() and path.name not in keep_names:
            trash_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(trash_dir / path.name))
