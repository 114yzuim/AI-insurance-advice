import json
import pathlib
import sqlite3
from contextlib import contextmanager

DB_PATH = pathlib.Path(__file__).parent / "advisor.db"

_JSON_COLS = {
    "children_ages", "planning_goals", "selected_modules",
    "assets", "liabilities",
    "preferred_channels", "retire_income_sources", "retire_dreams",
    "interested_topics", "risk_factors",
}


@contextmanager
def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def row_to_dict(row) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    for key in _JSON_COLS:
        if key in d and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError):
                pass
    return d
