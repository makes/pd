import re

from pd import db, scene_id


def test_generate_code_format():
    code = scene_id.generate_code()
    assert re.fullmatch(r"[0-9A-Z]{4}", code)
    assert not scene_id.REPEATED.search(code)


def test_generate_avoids_db_collision(tmp_path, monkeypatch):
    db.init_db(tmp_path)
    conn = db.connect(tmp_path / "pd.sqlite")
    conn.execute("INSERT INTO scene (scene_id) VALUES ('A7BN')")

    candidates = iter(["A7BN", "B2CD"])
    monkeypatch.setattr(scene_id, "generate_code", lambda: next(candidates))

    code = scene_id.generate(conn)
    conn.close()
    assert code == "B2CD"


def test_in_blocklist_resolves_regardless_of_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert scene_id.in_blocklist("1007") is True
    assert scene_id.in_blocklist("ZZZZ_NOT_A_REAL_CODE") is False
