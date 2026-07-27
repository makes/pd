from pd import db, paths, report


def make_project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    for d in paths.ProjectPaths(root).all_dirs():
        d.mkdir(parents=True)
    db.init_db(root)
    return root, paths.ProjectPaths(root)


def insert_clip(conn, *, clip_id, scene_id, start_ts, end_ts, source_hash="h", active=True):
    if not db.scene_id_exists(conn, scene_id):
        db.insert_scene(conn, scene_id)
    db.insert_clip(
        conn,
        clip_id=clip_id,
        scene_id=scene_id,
        start_ts=start_ts,
        end_ts=end_ts,
        screenshot_ts=start_ts,
        source_filename="f.mp4",
        source_dir="/videos",
        source_hash=source_hash,
        source_size=100,
    )
    if not active:
        db.toggle_clip_active(conn, clip_id)
    conn.commit()


def test_format_size():
    assert report._format_size(0) == "0.0 B"
    assert report._format_size(2048) == "2.0 KB"
    assert report._format_size(5 * 1024 * 1024) == "5.0 MB"


def test_duration_distribution_buckets(tmp_path):
    root, project_paths = make_project(tmp_path)
    conn = db.connect(project_paths.db)
    insert_clip(conn, clip_id="c0000001", scene_id="AAAA", start_ts="0", end_ts="5")  # <=10s
    insert_clip(conn, clip_id="c0000002", scene_id="AAAA", start_ts="0", end_ts="15")  # 10-20s
    insert_clip(conn, clip_id="c0000003", scene_id="AAAA", start_ts="0", end_ts="90")  # >60s
    insert_clip(
        conn, clip_id="c0000004", scene_id="AAAA", start_ts="0", end_ts="5", active=False
    )  # excluded

    dist = report._duration_distribution(conn)
    assert dist["<= 10s"] == 1
    assert dist["10-20s"] == 1
    assert dist["> 60s"] == 1
    assert sum(dist.values()) == 3
    conn.close()


def test_count_overlaps_only_same_hash_different_scene(tmp_path):
    root, project_paths = make_project(tmp_path)
    conn = db.connect(project_paths.db)
    # overlapping, different scene, same hash -> counts
    insert_clip(conn, clip_id="c0000001", scene_id="AAAA", start_ts="0", end_ts="10", source_hash="h1")
    insert_clip(conn, clip_id="c0000002", scene_id="BBBB", start_ts="5", end_ts="15", source_hash="h1")
    # overlapping but same scene -> excluded
    insert_clip(conn, clip_id="c0000003", scene_id="AAAA", start_ts="0", end_ts="10", source_hash="h2")
    insert_clip(conn, clip_id="c0000004", scene_id="AAAA", start_ts="5", end_ts="15", source_hash="h2")
    # non-overlapping, different scene, same hash -> excluded
    insert_clip(conn, clip_id="c0000005", scene_id="CCCC", start_ts="0", end_ts="10", source_hash="h3")
    insert_clip(conn, clip_id="c0000006", scene_id="DDDD", start_ts="20", end_ts="30", source_hash="h3")

    assert report._count_overlaps(conn) == 1
    conn.close()


def test_active_clip_scene_counts(tmp_path):
    root, project_paths = make_project(tmp_path)
    conn = db.connect(project_paths.db)
    db.insert_scene(conn, "ZERO")  # 0 clips at all -> 0 active
    insert_clip(conn, clip_id="c0000001", scene_id="ONE", start_ts="0", end_ts="5")
    insert_clip(conn, clip_id="c0000002", scene_id="TWO", start_ts="0", end_ts="5")
    insert_clip(conn, clip_id="c0000003", scene_id="TWO", start_ts="10", end_ts="15")

    zero, multiple = report._active_clip_scene_counts(conn)
    assert zero == 1
    assert multiple == 1
    conn.close()


def test_build_report_and_run_writes_timestamped_file(tmp_path, capsys):
    root, project_paths = make_project(tmp_path)
    conn = db.connect(project_paths.db)
    insert_clip(conn, clip_id="c0000001", scene_id="AAAA", start_ts="0", end_ts="5")
    conn.close()

    (project_paths.video / "AAAA_001_c0000001.mp4").write_bytes(b"x" * 10)
    (project_paths.screenshots / "AAAA_001_c0000001.jpg").write_bytes(b"y" * 20)

    report.run(root)

    captured = capsys.readouterr()
    assert "Scenes: 1" in captured.out
    assert "Video files: 1" in captured.out

    report_files = list(project_paths.report.iterdir())
    assert len(report_files) == 1
    assert report_files[0].read_text(encoding="utf-8") == captured.out.rstrip("\n")
