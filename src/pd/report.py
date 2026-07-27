import sqlite3
from datetime import datetime
from pathlib import Path

from . import db, paths

DURATION_THRESHOLDS = [10, 20, 30, 40, 50, 60]
DURATION_LABELS = ["<= 10s", "10-20s", "20-30s", "30-40s", "40-50s", "50-60s", "> 60s"]


def run(root: Path) -> None:
    project_paths = paths.ProjectPaths(root)
    conn = db.connect(project_paths.db)
    try:
        text = build_report(conn, project_paths)
    finally:
        conn.close()

    print(text)

    project_paths.report.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (project_paths.report / f"{timestamp}.txt").write_text(text, encoding="utf-8")


def build_report(conn: sqlite3.Connection, project_paths: paths.ProjectPaths) -> str:
    lines = [f"pd report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ""]

    scene_count = conn.execute("SELECT COUNT(*) FROM scene").fetchone()[0]
    actor_count = conn.execute("SELECT COUNT(*) FROM actor").fetchone()[0]
    actress_count = conn.execute("SELECT COUNT(*) FROM actress").fetchone()[0]
    lines += [f"Scenes: {scene_count}", f"Actors: {actor_count}", f"Actresses: {actress_count}", ""]

    video_count, video_size = _dir_stats(project_paths.video)
    screenshot_count, screenshot_size = _dir_stats(project_paths.screenshots)
    lines += [
        f"Video files: {video_count} ({_format_size(video_size)})",
        f"Screenshot files: {screenshot_count} ({_format_size(screenshot_size)})",
        "",
    ]

    trash_video_count, trash_video_size = _dir_stats(project_paths.trash_video)
    trash_screenshot_count, trash_screenshot_size = _dir_stats(project_paths.trash_screenshots)
    trash_total = trash_video_size + trash_screenshot_size
    lines += [
        f"Trash: {trash_video_count} videos, {trash_screenshot_count} screenshots "
        f"({_format_size(trash_total)} total)",
        "",
    ]

    lines.append("Clip duration distribution (active clips):")
    for label, count in _duration_distribution(conn).items():
        lines.append(f"  {label}: {count}")
    lines.append("")

    lines.append(f"Overlapping clips with different scene_id: {_count_overlaps(conn)}")
    lines.append("")

    zero, multiple = _active_clip_scene_counts(conn)
    lines.append(f"Scenes with 0 active clips: {zero}")
    lines.append(f"Scenes with more than 1 active clip: {multiple}")

    return "\n".join(lines)


def _dir_stats(directory: Path) -> tuple[int, int]:
    if not directory.is_dir():
        return 0, 0
    files = [p for p in directory.iterdir() if p.is_file()]
    return len(files), sum(p.stat().st_size for p in files)


def _format_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def _duration_distribution(conn: sqlite3.Connection) -> dict[str, int]:
    counts = dict.fromkeys(DURATION_LABELS, 0)
    rows = conn.execute("SELECT start_ts, end_ts FROM clip WHERE active = 1").fetchall()
    for row in rows:
        duration = float(row["end_ts"]) - float(row["start_ts"])
        counts[_bucket_label(duration)] += 1
    return counts


def _bucket_label(duration: float) -> str:
    for threshold, label in zip(DURATION_THRESHOLDS, DURATION_LABELS):
        if duration <= threshold:
            return label
    return DURATION_LABELS[-1]


def _count_overlaps(conn: sqlite3.Connection) -> int:
    rows = conn.execute("SELECT scene_id, source_hash, start_ts, end_ts FROM clip").fetchall()
    by_hash: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        by_hash.setdefault(row["source_hash"], []).append(row)

    count = 0
    for group in by_hash.values():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                if a["scene_id"] == b["scene_id"]:
                    continue
                if float(a["start_ts"]) < float(b["end_ts"]) and float(b["start_ts"]) < float(
                    a["end_ts"]
                ):
                    count += 1
    return count


def _active_clip_scene_counts(conn: sqlite3.Connection) -> tuple[int, int]:
    rows = conn.execute(
        "SELECT scene.scene_id AS scene_id, COUNT(clip.clip_id) AS active_count "
        "FROM scene LEFT JOIN clip ON clip.scene_id = scene.scene_id AND clip.active = 1 "
        "GROUP BY scene.scene_id"
    ).fetchall()
    zero = sum(1 for row in rows if row["active_count"] == 0)
    multiple = sum(1 for row in rows if row["active_count"] > 1)
    return zero, multiple
