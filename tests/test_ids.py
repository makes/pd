import re

from pd import db, ids


def test_generate_clip_id_format(tmp_path):
    db.init_db(tmp_path)
    conn = db.connect(tmp_path / "pd.sqlite")
    code = ids.generate_clip_id(conn)
    conn.close()
    assert re.fullmatch(r"[0-9a-f]{7}", code)


def test_generate_clip_id_avoids_collision(tmp_path, monkeypatch):
    db.init_db(tmp_path)
    conn = db.connect(tmp_path / "pd.sqlite")
    conn.execute("INSERT INTO scene (scene_id) VALUES ('A7BN')")
    conn.execute(
        "INSERT INTO clip (clip_id, scene_id, start_ts, end_ts, screenshot_ts, "
        "source_filename, source_hash, source_size) "
        "VALUES ('0000000', 'A7BN', '0', '1', '0', 'f.mp4', 'h', 1)"
    )

    candidates = iter([0x0000000, 0x1111111])
    monkeypatch.setattr(ids.secrets, "randbits", lambda n: next(candidates))

    code = ids.generate_clip_id(conn)
    conn.close()
    assert code == "1111111"
