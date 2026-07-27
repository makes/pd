import random
import re
import sqlite3
import string
from pathlib import Path

from . import db

ALPHABET = string.digits + string.ascii_uppercase

# Matches any run of 3 or more identical characters (e.g. 111, AAA, 7777)
REPEATED = re.compile(r"(.)\1{2,}")

BLOCKLIST_PATH = Path(__file__).parent / "reserved_scene_ids.txt"


def in_blocklist(code, filename=BLOCKLIST_PATH):
    try:
        with open(filename, encoding="utf-8") as f:
            return any(line.strip().upper() == code for line in f)
    except FileNotFoundError:
        return False


def generate_code():
    while True:
        code = (
            random.choice(ALPHABET[1:]) +
            "".join(random.choices(ALPHABET, k=3))
        )

        if REPEATED.search(code):
            continue

        if in_blocklist(code):
            continue

        return code


def generate(conn: sqlite3.Connection) -> str:
    while True:
        code = generate_code()
        if not db.scene_id_exists(conn, code):
            return code


if __name__ == "__main__":
    print(generate_code())
