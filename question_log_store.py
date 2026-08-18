"""
question_log_store.py
------------------------
Teacher dashboard ke liye question-activity log. PEHLE ye flat CSV
(`logs/question_log.csv`) mein tha — jo sirf usi Streamlit Cloud
container ke andar visible hota tha. Agar student app (`app.py`) aur
teacher dashboard (`dashboard.py`) ALAG apps ke tor par deploy hon
(jaisa is project mein hua — "plotlab-classroom" aur "plotlab-teacher"
do alag URLs/deployments hain), to har app ka apna, isolated container
hota hai, aur ek app ki likhi CSV file doosre app ko kabhi nazar nahi
aati — isi wajah se dashboard hamesha khali dikh raha tha, chahe
student app mein kitne bhi sawal poochhe gaye hon.

Fix: same shared connection (dekhein db_connection.py — local SQLite ya
Turso) use karte hain jo cache_store.py bhi use karta hai, taake dono
apps SAME database dekh sakein (agar Turso configure ho)."""

from __future__ import annotations

import threading
from pathlib import Path

import pandas as pd

_SCHEMA = """
CREATE TABLE IF NOT EXISTS question_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    course TEXT NOT NULL,
    question TEXT NOT NULL,
    matched_chapter TEXT,
    matched_section TEXT,
    similarity REAL,
    grounding TEXT,
    verified TEXT,
    repeated_confusion INTEGER,
    from_cache INTEGER,
    student_id TEXT,
    used_full_reveal INTEGER,
    mode TEXT,
    had_scaffold INTEGER
);
"""

# Phase 1 (schema-only): student_id, used_full_reveal, mode — teenon abhi
# sirf schema/storage layer mein hain. Koi caller (app.py) inhe abhi
# populate nahi kar raha — jaan-boojh kar. Pehle live Turso DB (jo dono
# deployed apps share karte hain) par ye migration land karo aur khud
# verify karo koi crash nahi hua, PHIR (Phase 2/3) feature-UI layer karo
# jo inhe actually bharay. Isse blast-radius chhota rehta hai.
#
# had_scaffold (build-order item 6, Aug 2026): app.py Section 3 mein
# `used_full_reveal = (always_full or not has_scaffold)` compute karta
# hai — matlab agar koi scaffold hi available nahi tha (not_found rows,
# ya purani cache jisme hint field hi nahi thi), used_full_reveal FORCE
# True ho jata hai, chahe student ne kuch skip na kiya ho. Dashboard ka
# engagement-metric (item 6) is ambiguity ko accurately measure nahi kar
# sakta tha — is column se ab clearly pata chalta hai ke scaffold KABHI
# available tha bhi ya nahi.
_MIGRATIONS = [
    "ALTER TABLE question_log ADD COLUMN student_id TEXT",
    "ALTER TABLE question_log ADD COLUMN used_full_reveal INTEGER",
    "ALTER TABLE question_log ADD COLUMN mode TEXT",
    "ALTER TABLE question_log ADD COLUMN had_scaffold INTEGER",
]

COLUMNS = [
    "timestamp", "course", "question", "matched_chapter", "matched_section",
    "similarity", "grounding", "verified", "repeated_confusion", "from_cache",
    "student_id", "used_full_reveal", "mode", "had_scaffold",
]


class QuestionLogStore:
    def __init__(self, db_path: str = "cache/qa_cache.db", connection=None):
        if connection is not None:
            self._conn = connection
        else:
            import sqlite3

            path = Path(db_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._apply_migrations()

    def _apply_migrations(self):
        """Idempotent schema migrations for SQLite and real Turso.

        ALTER TABLE ... ADD COLUMN behaves differently across SQLite and
        Turso/libsql when the column already exists. Instead of relying on
        the duplicate-column error text, inspect the schema first and only
        add columns that are actually missing.
        """
        with self._lock:
            rows = self._conn.execute(
                "PRAGMA table_info(question_log)"
            ).fetchall()

            existing_columns = {row[1] for row in rows}

            for stmt in _MIGRATIONS:
                # Each migration is:
                # ALTER TABLE question_log ADD COLUMN <name> <type>
                column_name = stmt.split("ADD COLUMN", 1)[1].strip().split()[0]

                if column_name in existing_columns:
                    continue

                self._conn.execute(stmt)
                self._conn.commit()
                existing_columns.add(column_name)

    def log_question(self, timestamp, course, question, matched_chapter, matched_section,
                      similarity, grounding, verified, repeated_confusion, from_cache,
                      student_id=None, used_full_reveal=None, mode="question", had_scaffold=None):
        """Return karta hai naye row ka id (SQLite ya Turso dono se
        `.lastrowid` milta hai — dekhein db_connection.py). Scaffolding
        feature (build-order item 3) isse `mark_revealed()` ke liye
        use karta hai — jab student baad mein "Show full solution"
        click kare (ek alag Streamlit rerun mein), to hum NAYI row nahi
        banate, isi row ko update karte hain."""
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO question_log "
                "(timestamp, course, question, matched_chapter, matched_section, "
                "similarity, grounding, verified, repeated_confusion, from_cache, "
                "student_id, used_full_reveal, mode, had_scaffold) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    timestamp, course, question, matched_chapter, matched_section,
                    similarity, grounding,
                    "" if verified is None else str(verified),
                    int(bool(repeated_confusion)),
                    int(bool(from_cache)),
                    student_id,
                    None if used_full_reveal is None else int(bool(used_full_reveal)),
                    mode,
                    None if had_scaffold is None else int(bool(had_scaffold)),
                ),
            )
            self._conn.commit()
            return cursor.lastrowid

    def mark_revealed(self, row_id):
        """Scaffolding (build-order item 3): jab student "Show full
        solution" par click kare, us specific row ka used_full_reveal
        1 par update karta hai — NAYI row nahi banate (ek sawaal = ek
        row, chahe reveal turant ho ya baad mein)."""
        if row_id is None:
            return
        with self._lock:
            self._conn.execute(
                "UPDATE question_log SET used_full_reveal = 1 WHERE id = ?",
                (row_id,),
            )
            self._conn.commit()

    def get_dataframe(self) -> pd.DataFrame:
        """dashboard.py ke liye — pehle `pd.read_csv(LOG_FILE)` tha, ab
        yahan se aata hai. Empty ho to bhi sahi columns wala empty
        DataFrame deta hai (dashboard ka "no data yet" check chalta rahe)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT " + ", ".join(COLUMNS) + " FROM question_log ORDER BY timestamp"
            ).fetchall()
        return pd.DataFrame(list(rows), columns=COLUMNS)