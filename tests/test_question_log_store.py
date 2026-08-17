import pandas as pd
import pytest

from question_log_store import QuestionLogStore, COLUMNS


@pytest.fixture
def store(tmp_path):
    db_path = tmp_path / "test_log.db"
    return QuestionLogStore(str(db_path))


class TestQuestionLogStore:
    def test_empty_log_returns_empty_dataframe_with_correct_columns(self, store):
        df = store.get_dataframe()
        assert len(df) == 0
        assert list(df.columns) == COLUMNS

    def test_log_question_then_retrieve(self, store):
        store.log_question(
            timestamp="2026-08-05T10:00:00",
            course="Calculus",
            question="derivative of x^2",
            matched_chapter="Ch1",
            matched_section="Derivatives",
            similarity=0.92,
            grounding="direct_from_notes",
            verified=None,
            repeated_confusion=False,
            from_cache=False,
        )
        df = store.get_dataframe()
        assert len(df) == 1
        assert df.iloc[0]["course"] == "Calculus"
        assert df.iloc[0]["question"] == "derivative of x^2"
        assert df.iloc[0]["from_cache"] == 0
        assert df.iloc[0]["repeated_confusion"] == 0

    def test_boolean_fields_stored_as_int(self, store):
        store.log_question(
            timestamp="2026-08-05T10:00:00", course="Calculus", question="q",
            matched_chapter="", matched_section="", similarity=0.5,
            grounding="adapted_by_ai", verified=True,
            repeated_confusion=True, from_cache=True,
        )
        df = store.get_dataframe()
        assert df.iloc[0]["from_cache"] == 1
        assert df.iloc[0]["repeated_confusion"] == 1
        assert df.iloc[0]["verified"] == "True"

    def test_multiple_entries_ordered_by_timestamp(self, store):
        for i, ts in enumerate(["2026-08-05T10:00:00", "2026-08-05T09:00:00", "2026-08-05T11:00:00"]):
            store.log_question(
                timestamp=ts, course="Calculus", question=f"q{i}",
                matched_chapter="", matched_section="", similarity=0.5,
                grounding="direct_from_notes", verified=None,
                repeated_confusion=False, from_cache=False,
            )
        df = store.get_dataframe()
        assert len(df) == 3
        timestamps = pd.to_datetime(df["timestamp"]).tolist()
        assert timestamps == sorted(timestamps)  # confirms ORDER BY timestamp worked

    def test_shared_connection_across_two_store_instances(self, tmp_path):
        # Simulates two apps (teacher + student) pointed at the SAME db file
        import sqlite3
        db_path = str(tmp_path / "shared.db")
        conn1 = sqlite3.connect(db_path, check_same_thread=False)
        conn2 = sqlite3.connect(db_path, check_same_thread=False)

        store1 = QuestionLogStore(connection=conn1)
        store1.log_question(
            timestamp="2026-08-05T10:00:00", course="Calculus", question="from store1",
            matched_chapter="", matched_section="", similarity=0.5,
            grounding="direct_from_notes", verified=None,
            repeated_confusion=False, from_cache=False,
        )

        store2 = QuestionLogStore(connection=conn2)
        df = store2.get_dataframe()
        assert len(df) == 1
        assert df.iloc[0]["question"] == "from store1"


class TestSchemaMigration:
    """Section 1 (Aug 2026): student_id/used_full_reveal/mode columns.
    Sabse important scenario: production Turso table 'question_log'
    ALREADY EXISTS bina in columns ke (dono live apps abhi use kar rahe
    hain). CREATE TABLE IF NOT EXISTS is case mein kuch nahi karta —
    migration ko explicitly ye columns add karne hain, bina crash kiye,
    aur bina purana data ganwaye."""

    def test_migration_adds_columns_to_pre_existing_old_schema_table(self, tmp_path):
        import sqlite3

        db_path = str(tmp_path / "old_schema.db")
        conn = sqlite3.connect(db_path, check_same_thread=False)
        # Purana (pre-migration) schema — jaisa abhi production Turso mein hai
        conn.executescript("""
            CREATE TABLE question_log (
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
        """)
        conn.execute(
            "INSERT INTO question_log (timestamp, course, question, matched_chapter, "
            "matched_section, similarity, grounding, verified, repeated_confusion, from_cache) "
            "VALUES ('2026-08-01T09:00:00', 'Calculus', 'old question', 'Ch1', 'Sec1', 0.9, "
            "'direct_from_notes', '', 0, 0)"
        )
        conn.commit()

        # Ye simulate karta hai app restart / redeploy jab naya code purani table se milta hai
        store = QuestionLogStore(connection=conn)

        df = store.get_dataframe()
        assert len(df) == 1
        # Purani row zinda hai aur naye columns None hain — crash nahi hua
        assert df.iloc[0]["question"] == "old question"
        assert df.iloc[0]["student_id"] is None
        assert df.iloc[0]["used_full_reveal"] is None
        assert df.iloc[0]["mode"] is None
        assert df.iloc[0]["had_scaffold"] is None

    def test_migration_is_idempotent_across_repeated_instantiation(self, tmp_path):
        # Streamlit Cloud har request/rerun par QuestionLogStore() naya
        # instantiate kar sakta hai — migration baar baar chalne se
        # crash nahi honi chahiye
        db_path = str(tmp_path / "repeat.db")
        QuestionLogStore(db_path)
        QuestionLogStore(db_path)
        store = QuestionLogStore(db_path)  # teesri baar bhi crash na ho
        assert list(store.get_dataframe().columns) == COLUMNS

    def test_new_columns_default_correctly_when_not_provided(self, store):
        # Backward-compat: purane call sites (jo abhi naye params pass
        # nahi karte) crash nahi karne chahiye, aur sensible defaults milne chahiyein
        store.log_question(
            timestamp="2026-08-15T10:00:00", course="Calculus", question="q",
            matched_chapter="", matched_section="", similarity=0.5,
            grounding="direct_from_notes", verified=None,
            repeated_confusion=False, from_cache=False,
        )
        df = store.get_dataframe()
        assert df.iloc[0]["student_id"] is None
        assert df.iloc[0]["used_full_reveal"] is None
        assert df.iloc[0]["mode"] == "question"

    def test_new_columns_store_provided_values(self, store):
        store.log_question(
            timestamp="2026-08-15T10:00:00", course="Calculus", question="q",
            matched_chapter="", matched_section="", similarity=0.5,
            grounding="adapted_by_ai", verified=True,
            repeated_confusion=False, from_cache=False,
            student_id="Ali Raza", used_full_reveal=True, mode="diagnosis_v0",
        )
        df = store.get_dataframe()
        assert df.iloc[0]["student_id"] == "Ali Raza"
        assert df.iloc[0]["used_full_reveal"] == 1
        assert df.iloc[0]["mode"] == "diagnosis_v0"

class TestRevealTracking:
    """Section 3 (scaffolding, Aug 2026): log_question() ab row id
    return karta hai, aur mark_revealed() us row ko baad mein update
    kar sakta hai — jab student turant nahi, thodi der baad "Show full
    solution" click kare (ek alag Streamlit rerun mein)."""

    def test_log_question_returns_a_row_id(self, store):
        row_id = store.log_question(
            timestamp="2026-08-16T10:00:00", course="Calculus", question="q",
            matched_chapter="", matched_section="", similarity=0.5,
            grounding="adapted_by_ai", verified=None,
            repeated_confusion=False, from_cache=False,
        )
        assert row_id is not None
        assert isinstance(row_id, int)

    def test_mark_revealed_updates_only_the_targeted_row(self, store):
        row_id_1 = store.log_question(
            timestamp="2026-08-16T10:00:00", course="Calculus", question="q1",
            matched_chapter="", matched_section="", similarity=0.5,
            grounding="adapted_by_ai", verified=None,
            repeated_confusion=False, from_cache=False, used_full_reveal=False,
        )
        row_id_2 = store.log_question(
            timestamp="2026-08-16T10:01:00", course="Calculus", question="q2",
            matched_chapter="", matched_section="", similarity=0.5,
            grounding="adapted_by_ai", verified=None,
            repeated_confusion=False, from_cache=False, used_full_reveal=False,
        )

        store.mark_revealed(row_id_1)

        df = store.get_dataframe().set_index("question")
        assert df.loc["q1", "used_full_reveal"] == 1  # click hua
        assert df.loc["q2", "used_full_reveal"] == 0  # ye touch nahi hui
        assert row_id_1 != row_id_2

    def test_mark_revealed_with_none_is_a_safe_noop(self, store):
        # app.py mein agar kabhi log_row_id capture na ho paya ho (jaise
        # logging khud fail ho gayi thi try/except mein), mark_revealed
        # ko None mil sakta hai — crash nahi hona chahiye
        store.mark_revealed(None)  # crash na ho, bas itna hi check hai
class TestHadScaffold:
    """Build-order item 6 (Aug 2026). used_full_reveal akela ye batane
    ke liye kaafi nahi tha ke scaffold GENUINELY available tha ya nahi
    (dekhein app.py: has_scaffold False hone par used_full_reveal FORCE
    True hota hai) — had_scaffold is ambiguity ko explicitly resolve
    karta hai, taake dashboard ka engagement-metric accurate ho."""

    def test_defaults_to_none_when_not_provided(self, store):
        # Diagnosis-mode rows (jinke liye scaffolding apply hi nahi hoti)
        # ye default use karengi
        store.log_question(
            timestamp="2026-08-16T10:00:00", course="Calculus", question="q",
            matched_chapter="", matched_section="", similarity=0.5,
            grounding="adapted_by_ai", verified=True,
            repeated_confusion=False, from_cache=False,
        )
        df = store.get_dataframe()
        assert df.iloc[0]["had_scaffold"] is None

    def test_stores_true_and_false_explicitly(self, store):
        store.log_question(
            timestamp="2026-08-16T10:00:00", course="Calculus", question="had scaffold",
            matched_chapter="", matched_section="", similarity=0.5,
            grounding="adapted_by_ai", verified=True,
            repeated_confusion=False, from_cache=False, had_scaffold=True,
        )
        store.log_question(
            timestamp="2026-08-16T10:01:00", course="Calculus", question="no scaffold (not_found)",
            matched_chapter="", matched_section="", similarity=0.0,
            grounding="not_found", verified=None,
            repeated_confusion=False, from_cache=False, had_scaffold=False,
        )
        df = store.get_dataframe().set_index("question")
        assert df.loc["had scaffold", "had_scaffold"] == 1
        assert df.loc["no scaffold (not_found)", "had_scaffold"] == 0