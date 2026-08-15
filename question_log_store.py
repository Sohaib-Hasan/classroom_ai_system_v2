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
    mode TEXT
);
"""

# Phase 1 (schema-only): student_id, used_full_reveal, mode — teenon abhi
# sirf schema/storage layer mein hain. Koi caller (app.py) inhe abhi
# populate nahi kar raha — jaan-boojh kar. Pehle live Turso DB (jo dono
# deployed apps share karte hain) par ye migration land karo aur khud
# verify karo koi crash nahi hua, PHIR (Phase 2/3) feature-UI layer karo
# jo inhe actually bharay. Isse blast-radius chhota rehta hai.
_MIGRATIONS = [
    "ALTER TABLE question_log ADD COLUMN student_id TEXT",
    "ALTER TABLE question_log ADD COLUMN used_full_reveal INTEGER",
    "ALTER TABLE question_log ADD COLUMN mode TEXT",
]

COLUMNS = [
    "timestamp", "course", "question", "matched_chapter", "matched_section",
    "similarity", "grounding", "verified", "repeated_confusion", "from_cache",
    "student_id", "used_full_reveal", "mode",
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
        """Idempotent, safe to re-run har baar app start hone par.
        Fresh DBs (student_id waghera already _SCHEMA mein) yahan
        "duplicate column" hit karke chup-chaap skip ho jayenge. Purani,
        already-deployed Turso table (jisme ye columns nahi thay jab
        pehli baar bani thi) inhe yahan se add karegi. Sirf EXPECTED
        error (column already exists) ko ignore karte hain — koi aur
        wajah se fail ho (jaise connection hi na bane) to raise hoga,
        chup nahi karayenge (Turso/network issues silently miss nahi
        hone chahiyein)."""
        with self._lock:
            for stmt in _MIGRATIONS:
                try:
                    self._conn.execute(stmt)
                    self._conn.commit()
                except Exception as e:
                    msg = str(e).lower()
                    if "duplicate column" in msg or "already exists" in msg:
                        continue
                    raise

    def log_question(self, timestamp, course, question, matched_chapter, matched_section,
                      similarity, grounding, verified, repeated_confusion, from_cache,
                      student_id=None, used_full_reveal=None, mode="question"):
        with self._lock:
            self._conn.execute(
                "INSERT INTO question_log "
                "(timestamp, course, question, matched_chapter, matched_section, "
                "similarity, grounding, verified, repeated_confusion, from_cache, "
                "student_id, used_full_reveal, mode) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    timestamp, course, question, matched_chapter, matched_section,
                    similarity, grounding,
                    "" if verified is None else str(verified),
                    int(bool(repeated_confusion)),
                    int(bool(from_cache)),
                    student_id,
                    None if used_full_reveal is None else int(bool(used_full_reveal)),
                    mode,
                ),
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