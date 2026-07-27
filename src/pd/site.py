import html
import sqlite3
from pathlib import Path

from PIL import Image

from . import db, paths

THUMBNAIL_MAX_SIZE = (320, 320)

PAGE_TEMPLATE = """<!doctype html>
<html>
<head><meta charset="utf-8"><title>{title}</title></head>
<body>
<h1>{heading}</h1>
{body}
</body>
</html>
"""


def run(root: Path, category: str | None = None) -> None:
    project_paths = paths.ProjectPaths(root)
    conn = db.connect(project_paths.db)
    try:
        sync_thumbnails(project_paths)
        all_categories = sorted(_all_categories(conn))
        categories = [category] if category else all_categories
        for cat in categories:
            _write_category_page(conn, project_paths, cat)
        _write_index(project_paths, all_categories)
    finally:
        conn.close()


def _all_categories(conn: sqlite3.Connection) -> set[str]:
    return {row["category"] for row in conn.execute("SELECT DISTINCT category FROM scene")}


def sync_thumbnails(project_paths: paths.ProjectPaths) -> None:
    project_paths.thumbnails.mkdir(parents=True, exist_ok=True)
    screenshot_names = {p.name for p in project_paths.screenshots.iterdir() if p.is_file()}

    for name in screenshot_names:
        thumb_path = project_paths.thumbnails / name
        if thumb_path.exists():
            continue
        with Image.open(project_paths.screenshots / name) as img:
            img.thumbnail(THUMBNAIL_MAX_SIZE)
            img.convert("RGB").save(thumb_path)

    for thumb_path in project_paths.thumbnails.iterdir():
        if thumb_path.is_file() and thumb_path.name not in screenshot_names:
            thumb_path.unlink()


def _esc(value) -> str:
    return html.escape(str(value)) if value is not None else ""


def _scene_entry_html(conn: sqlite3.Connection, scene: sqlite3.Row) -> str | None:
    current_clip = db.get_latest_active_clip(conn, scene["scene_id"])
    if current_clip is None:
        return None

    seq = db.clip_seq(conn, scene["scene_id"], current_clip["clip_id"])
    screenshot_name = paths.screenshot_filename(scene["scene_id"], seq, current_clip["clip_id"])
    video_name = paths.video_filename(scene["scene_id"], seq, current_clip["clip_id"])

    links = db.get_scene_links(conn, scene["scene_id"])
    links_html = "".join(
        f'<li><a href="{html.escape(url)}">{html.escape(url)}</a></li>' for url in links
    )

    return f"""
    <div class="scene">
      <a href="image/screenshots/{html.escape(screenshot_name)}">
        <img src="thumbnails/{html.escape(screenshot_name)}" alt="{_esc(scene['title'])}">
      </a>
      <h2><a href="video/{html.escape(video_name)}">{_esc(video_name)}</a></h2>
      <p>Title: {_esc(scene['title'])}</p>
      <p>Category: {_esc(scene['category'])}</p>
      <p>Rating: {_esc(scene['rating'])}</p>
      <p>IMDB: {_esc(scene['imdb_url'])}</p>
      <p>Source filename: {_esc(current_clip['source_filename'])}</p>
      <p>Source hash: {_esc(current_clip['source_hash'])}</p>
      <p>Created: {_esc(scene['created'])}</p>
      <p>Description: {_esc(scene['description'])}</p>
      <ul class="links">{links_html}</ul>
    </div>
    """


def _write_category_page(
    conn: sqlite3.Connection, project_paths: paths.ProjectPaths, category: str
) -> None:
    scenes = conn.execute(
        "SELECT * FROM scene WHERE category = ? ORDER BY created DESC", (category,)
    ).fetchall()
    entries = [entry for scene in scenes if (entry := _scene_entry_html(conn, scene)) is not None]
    page = PAGE_TEMPLATE.format(
        title=html.escape(category),
        heading=f"Category: {html.escape(category)}",
        body="\n".join(entries),
    )
    (project_paths.content / f"{category}.html").write_text(page, encoding="utf-8")


def _write_index(project_paths: paths.ProjectPaths, categories: list[str]) -> None:
    links = "".join(
        f'<li><a href="{html.escape(cat)}.html">{html.escape(cat)}</a></li>' for cat in categories
    )
    page = PAGE_TEMPLATE.format(title="pd", heading="Categories", body=f"<ul>{links}</ul>")
    (project_paths.content / "index.html").write_text(page, encoding="utf-8")
