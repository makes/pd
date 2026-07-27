import secrets
import sqlite3

from . import db

CLIP_ID_LENGTH = 7


def generate_clip_id(conn: sqlite3.Connection) -> str:
    while True:
        code = f"{secrets.randbits(4 * CLIP_ID_LENGTH):0{CLIP_ID_LENGTH}x}"
        if not db.clip_id_exists(conn, code):
            return code
