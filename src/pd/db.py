import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE scene (
    scene_id text PRIMARY KEY,
    title text,
    category text NOT NULL DEFAULT 'C',
    rating int CHECK (rating IS NULL OR rating BETWEEN 0 AND 100),
    description text,
    imdb_url text,
    links text,
    metadata text,
    created timestamp NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
);

CREATE TABLE clip (
    clip_id text PRIMARY KEY,
    scene_id text NOT NULL REFERENCES scene(scene_id),
    start_ts text NOT NULL,
    end_ts text NOT NULL,
    screenshot_ts text NOT NULL,
    source_filename text NOT NULL,
    source_dir text,
    source_hash text NOT NULL,
    source_size int NOT NULL,
    active bool NOT NULL DEFAULT 1,
    created timestamp NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
);

CREATE TABLE actor (
    actor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name text NOT NULL,
    rating int CHECK (rating IS NULL OR rating BETWEEN 0 AND 100),
    intro text,
    image_file_1 text,
    image_file_2 text,
    imdb_url text,
    links text,
    metadata text,
    created timestamp NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
);

CREATE TABLE actress (
    actress_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name text NOT NULL,
    rating int CHECK (rating IS NULL OR rating BETWEEN 0 AND 100),
    intro text,
    image_file_1 text,
    image_file_2 text,
    imdb_url text,
    links text,
    metadata text,
    created timestamp NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
);

CREATE TABLE scene_actor (
    scene_id text NOT NULL REFERENCES scene(scene_id),
    actor_id int NOT NULL REFERENCES actor(actor_id),
    created timestamp NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
    PRIMARY KEY (scene_id, actor_id)
);

CREATE TABLE scene_actress (
    scene_id text NOT NULL REFERENCES scene(scene_id),
    actress_id int NOT NULL REFERENCES actress(actress_id),
    created timestamp NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
    PRIMARY KEY (scene_id, actress_id)
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(root: Path) -> None:
    db_path = root / "pd.sqlite"
    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def insert_scene(conn: sqlite3.Connection, scene_id: str, category: str = "C") -> None:
    conn.execute(
        "INSERT INTO scene (scene_id, category) VALUES (?, ?)", (scene_id, category)
    )


def insert_clip(
    conn: sqlite3.Connection,
    *,
    clip_id: str,
    scene_id: str,
    start_ts: str,
    end_ts: str,
    screenshot_ts: str,
    source_filename: str,
    source_dir: str | None,
    source_hash: str,
    source_size: int,
) -> None:
    conn.execute(
        """
        INSERT INTO clip (
            clip_id, scene_id, start_ts, end_ts, screenshot_ts,
            source_filename, source_dir, source_hash, source_size, active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (
            clip_id,
            scene_id,
            start_ts,
            end_ts,
            screenshot_ts,
            source_filename,
            source_dir,
            source_hash,
            source_size,
        ),
    )


def list_scenes(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM scene ORDER BY created DESC").fetchall()


def get_scene(conn: sqlite3.Connection, scene_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM scene WHERE scene_id = ?", (scene_id,)).fetchone()


def list_clips_for_scene(conn: sqlite3.Connection, scene_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM clip WHERE scene_id = ? ORDER BY created ASC", (scene_id,)
    ).fetchall()


def get_clip(conn: sqlite3.Connection, clip_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM clip WHERE clip_id = ?", (clip_id,)).fetchone()


def clip_seq(conn: sqlite3.Connection, scene_id: str, clip_id: str) -> int:
    """1-indexed rank of clip_id within its scene's clips, ordered oldest-created first."""
    clips = list_clips_for_scene(conn, scene_id)
    for i, clip in enumerate(clips, start=1):
        if clip["clip_id"] == clip_id:
            return i
    raise ValueError(f"clip {clip_id} not found in scene {scene_id}")


def get_latest_active_clip(conn: sqlite3.Connection, scene_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM clip WHERE scene_id = ? AND active = 1 ORDER BY created DESC LIMIT 1",
        (scene_id,),
    ).fetchone()


def toggle_clip_active(conn: sqlite3.Connection, clip_id: str) -> None:
    conn.execute("UPDATE clip SET active = NOT active WHERE clip_id = ?", (clip_id,))
    conn.commit()


def update_clip_scene_id(conn: sqlite3.Connection, clip_id: str, new_scene_id: str) -> None:
    conn.execute("UPDATE clip SET scene_id = ? WHERE clip_id = ?", (new_scene_id, clip_id))
    conn.commit()


SCENE_EDITABLE_FIELDS = ("title", "category", "rating", "imdb_url", "description")


def update_scene_field(conn: sqlite3.Connection, scene_id: str, field: str, value) -> None:
    if field not in SCENE_EDITABLE_FIELDS:
        raise ValueError(f"not an editable scene field: {field}")
    conn.execute(f"UPDATE scene SET {field} = ? WHERE scene_id = ?", (value, scene_id))
    conn.commit()


def find_or_create_actor(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute("SELECT actor_id FROM actor WHERE name = ?", (name,)).fetchone()
    if row is not None:
        return row["actor_id"]
    cur = conn.execute("INSERT INTO actor (name) VALUES (?)", (name,))
    conn.commit()
    return cur.lastrowid


def find_or_create_actress(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute("SELECT actress_id FROM actress WHERE name = ?", (name,)).fetchone()
    if row is not None:
        return row["actress_id"]
    cur = conn.execute("INSERT INTO actress (name) VALUES (?)", (name,))
    conn.commit()
    return cur.lastrowid


def add_scene_actor(conn: sqlite3.Connection, scene_id: str, actor_id: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO scene_actor (scene_id, actor_id) VALUES (?, ?)",
        (scene_id, actor_id),
    )
    conn.commit()


def remove_scene_actor(conn: sqlite3.Connection, scene_id: str, actor_id: int) -> None:
    conn.execute(
        "DELETE FROM scene_actor WHERE scene_id = ? AND actor_id = ?", (scene_id, actor_id)
    )
    conn.commit()


def list_scene_actors(conn: sqlite3.Connection, scene_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT actor.* FROM actor JOIN scene_actor ON actor.actor_id = scene_actor.actor_id "
        "WHERE scene_actor.scene_id = ? ORDER BY scene_actor.created ASC",
        (scene_id,),
    ).fetchall()


def add_scene_actress(conn: sqlite3.Connection, scene_id: str, actress_id: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO scene_actress (scene_id, actress_id) VALUES (?, ?)",
        (scene_id, actress_id),
    )
    conn.commit()


def remove_scene_actress(conn: sqlite3.Connection, scene_id: str, actress_id: int) -> None:
    conn.execute(
        "DELETE FROM scene_actress WHERE scene_id = ? AND actress_id = ?", (scene_id, actress_id)
    )
    conn.commit()


def list_scene_actresses(conn: sqlite3.Connection, scene_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT actress.* FROM actress "
        "JOIN scene_actress ON actress.actress_id = scene_actress.actress_id "
        "WHERE scene_actress.scene_id = ? ORDER BY scene_actress.created ASC",
        (scene_id,),
    ).fetchall()


def get_scene_links(conn: sqlite3.Connection, scene_id: str) -> list[str]:
    scene = get_scene(conn, scene_id)
    raw = scene["links"] if scene else None
    return json.loads(raw) if raw else []


def set_scene_links(conn: sqlite3.Connection, scene_id: str, links: list[str]) -> None:
    conn.execute("UPDATE scene SET links = ? WHERE scene_id = ?", (json.dumps(links), scene_id))
    conn.commit()


def scene_id_exists(conn: sqlite3.Connection, scene_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM scene WHERE scene_id = ?", (scene_id,)).fetchone()
    return row is not None


def clip_id_exists(conn: sqlite3.Connection, clip_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM clip WHERE clip_id = ?", (clip_id,)).fetchone()
    return row is not None
