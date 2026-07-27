import sqlite3
import subprocess
from pathlib import Path

from . import db, hash, ids, paths, scene_id


def generate_screenshot(source_path: Path, ts: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-ss", ts, "-i", str(source_path), "-frames:v", "1", str(output_path)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def create_scene_and_clip(
    conn: sqlite3.Connection,
    project_paths: paths.ProjectPaths,
    source_path: Path,
    start_ts: str,
    end_ts: str,
    screenshot_ts: str,
) -> tuple[str, str]:
    """Create a new scene + its first clip from a captured (start, end, screenshot) triple.

    Implements the "Data capture" workflow from DESIGN.md: id generation, scene/clip
    rows, and the preview screenshot for the new (only, so seq=1) clip in the scene.
    """
    new_scene_id = scene_id.generate(conn)
    clip_id = ids.generate_clip_id(conn)
    source_hash = hash.compute_file_hash(source_path)
    source_size = source_path.stat().st_size

    db.insert_scene(conn, new_scene_id)
    db.insert_clip(
        conn,
        clip_id=clip_id,
        scene_id=new_scene_id,
        start_ts=start_ts,
        end_ts=end_ts,
        screenshot_ts=screenshot_ts,
        source_filename=source_path.name,
        source_dir=str(source_path.parent),
        source_hash=source_hash,
        source_size=source_size,
    )
    conn.commit()

    screenshot_path = project_paths.screenshots / paths.screenshot_filename(
        new_scene_id, 1, clip_id
    )
    generate_screenshot(source_path, screenshot_ts, screenshot_path)

    return new_scene_id, clip_id
