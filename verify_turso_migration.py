"""
verify_turso_migration.py
----------------------------
MANUAL smoke-test — pytest suite ka hissa nahi (real Turso credentials
aur network chahiye). Section 1 (schema migration, Aug 2026) se leke ab
tak ye assumption baar baar flag hui hai lekin kabhi live confirm nahi
hui: Turso ka "duplicate column" error-wording SQLite (jis par saare
sandbox tests chalte hain) se match karta hai ya nahi —
`question_log_store.py::_apply_migrations()` sirf "duplicate column"/
"already exists" strings ko safe treat karta hai, baaki har error raise
karta hai. Agar Turso ka wording alag nikla, migration production mein
CRASH karegi jahan sandbox mein pass hui thi.

Ye script EXPLICITLY ek OLD schema table banata hai (jaisi migration se
pehle koi bhi already-deployed table hoti), phir QuestionLogStore() usse
connect karta hai aur migration chalne deta hai — bilkul wahi scenario
jo tests/test_question_log_store.py::TestSchemaMigration sandbox mein
simulate karta hai, is baar REAL Turso ke against.

⚠️  RECOMMENDATION: production Turso DB ke against seedha mat chalayein.
Pehle ek CHHOTI, ALAG scratch/test database banayein:
    turso db create classroom-ai-test
(ya Turso web dashboard se, agar CLI Windows Git Bash/MINGW mein na
chale — README.md ke "Shared storage (Turso)" section mein iska HTTP-
based alternative bhi hai). Sirf jab ye script scratch DB par cleanly
pass ho jaye, tabhi production database par bharosa karein — production
apne aap migrate ho jayegi jab app pehli baar start hogi, isse alag se
kuch nahi chalana.

Chalane se pehle: config.py mein TURSO_DATABASE_URL/TURSO_AUTH_TOKEN
set karein — SCRATCH database ke, production ke NAHI.

Chalana:
    python3 verify_turso_migration.py
"""

import sys

from config import TURSO_AUTH_TOKEN, TURSO_DATABASE_URL
from db_connection import TursoConnection
from question_log_store import QuestionLogStore

# Ye woh schema hai jo migration se PEHLE thi (student_id/used_full_reveal/
# mode/had_scaffold ke bina) — bilkul wahi jo test_question_log_store.py
# ::TestSchemaMigration sandbox mein banata hai.
_OLD_SCHEMA = """
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
    from_cache INTEGER
);
"""


def main():
    if not TURSO_DATABASE_URL or not TURSO_AUTH_TOKEN:
        print("config.py mein TURSO_DATABASE_URL/TURSO_AUTH_TOKEN set nahi hain — kuch test karne ko nahi hai.")
        sys.exit(0)

    print(f"Connecting to: {TURSO_DATABASE_URL}")
    print("⚠️  Confirm karein ye SCRATCH/TEST database hai, production nahi. Ctrl+C se abhi rok sakte hain.\n")

    conn = TursoConnection(TURSO_DATABASE_URL, TURSO_AUTH_TOKEN)

    print("Step 1/4 — OLD schema bana rahe hain (student_id/used_full_reveal/mode/had_scaffold ke bina)...")
    conn.executescript(_OLD_SCHEMA)
    conn.commit()
    conn.execute(
        "INSERT INTO question_log (timestamp, course, question, matched_chapter, "
        "matched_section, similarity, grounding, verified, repeated_confusion, from_cache) "
        "VALUES ('2026-08-01T09:00:00', 'Calculus', 'test question', 'Ch1', 'Sec1', 0.9, "
        "'direct_from_notes', '', 0, 0)"
    )
    conn.commit()
    print("   Done — 1 dummy row purane schema mein insert hui.\n")

    print("Step 2/4 — QuestionLogStore() se connect kar rahe hain, migration yahan chalegi...")
    try:
        store = QuestionLogStore(connection=conn)
    except Exception as e:
        print(f"\n❌ MIGRATION FAILED: {e!r}")
        print(
            "\nIska matlab Turso ka error-wording sandbox ke SQLite se match nahi karta —\n"
            "question_log_store.py::_apply_migrations() ko is real wording ke hisaab se\n"
            "update karna hoga (abhi sirf 'duplicate column'/'already exists' ignore karta hai).\n"
            "Actual error text upar dekhein aur us string ko _apply_migrations() mein add karein."
        )
        sys.exit(1)
    print("   Migration crash nahi hui.\n")

    print("Step 3/4 — confirm kar rahe hain purani row zinda hai aur naye columns None hain...")
    df = store.get_dataframe()
    assert len(df) == 1, f"Expected 1 row, got {len(df)}"
    assert df.iloc[0]["question"] == "test question"
    assert df.iloc[0]["student_id"] is None
    assert df.iloc[0]["had_scaffold"] is None
    print("   Confirmed — purana data crash ya loss ke bina zinda hai.\n")

    print("Step 4/4 — dobara QuestionLogStore() banate hain (idempotency check)...")
    store2 = QuestionLogStore(connection=conn)
    df2 = store2.get_dataframe()
    assert len(df2) == 1, "Dobara migration chalne se row duplicate ho gayi ya gum ho gayi"
    print("   Confirmed — dobara chalane se crash ya duplicate nahi hua.\n")

    print("✅ MIGRATION VERIFIED against real Turso.")
    print(
        "\nAgar ye scratch database thi, ab isse delete kar sakte hain:\n"
        "    turso db destroy <db-name>\n"
        "Production database apne aap migrate ho jayegi jab app pehli baar start hogi —\n"
        "isse alag se kuch chalane ki zaroorat nahi."
    )


if __name__ == "__main__":
    main()