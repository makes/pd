from pd import db


def test_init_db_creates_schema(tmp_path):
    db.init_db(tmp_path)
    conn = db.connect(tmp_path / "pd.sqlite")
    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        if row["name"] != "sqlite_sequence"
    }
    conn.close()
    assert tables == {"scene", "clip", "actor", "actress", "scene_actor", "scene_actress"}


def test_scene_id_exists(tmp_path):
    db.init_db(tmp_path)
    conn = db.connect(tmp_path / "pd.sqlite")
    assert not db.scene_id_exists(conn, "A7BN")
    conn.execute("INSERT INTO scene (scene_id) VALUES ('A7BN')")
    assert db.scene_id_exists(conn, "A7BN")
    conn.close()


def test_clip_id_exists(tmp_path):
    db.init_db(tmp_path)
    conn = db.connect(tmp_path / "pd.sqlite")
    assert not db.clip_id_exists(conn, "af5c68d")
    conn.execute("INSERT INTO scene (scene_id) VALUES ('A7BN')")
    conn.execute(
        "INSERT INTO clip (clip_id, scene_id, start_ts, end_ts, screenshot_ts, "
        "source_filename, source_hash, source_size) "
        "VALUES ('af5c68d', 'A7BN', '0', '1', '0', 'f.mp4', 'h', 1)"
    )
    assert db.clip_id_exists(conn, "af5c68d")
    conn.close()
