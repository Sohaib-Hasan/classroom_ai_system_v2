from session_helpers import is_new_diagnosis_upload, reset_identity


class TestResetIdentity:
    """Regression test (16 Aug 2026, mentor-caught bug): shared/lab
    computer scenario — Student A asks questions, clicks "Change name",
    Student B types their own name. Student B must NOT see Student A's
    chat history. Pehli version sirf student_id clear karti thi,
    messages nahi — is se ye exact scenario break hota tha."""

    def test_clears_both_student_id_and_messages(self):
        session_state = {
            "student_id": "Ali Raza",
            "messages": [
                {"question": "derivative of x^2", "answer": "some cached answer object"},
                {"question": "follow-up question", "answer": "another answer object"},
            ],
        }
        reset_identity(session_state)
        assert session_state["student_id"] is None
        assert session_state["messages"] == []

    def test_safe_to_call_when_messages_already_empty(self):
        session_state = {"student_id": "Sara", "messages": []}
        reset_identity(session_state)
        assert session_state["student_id"] is None
        assert session_state["messages"] == []

    def test_works_against_a_dict_like_streamlit_session_state_stand_in(self):
        # st.session_state khud dict-style ITEM access support karta hai
        # (session_state["x"]), attribute-style ke ilawa — isi wajah se
        # reset_identity() dono ke sath kaam karta hai, plain dict yahan
        # us behavior ko simulate karta hai bina asli Streamlit runtime ke.
        class FakeSessionState(dict):
            pass

        session_state = FakeSessionState(student_id="Bilal", messages=[{"question": "q"}])
        reset_identity(session_state)
        assert session_state["student_id"] is None
        assert session_state["messages"] == []


class _FakeUploadedFile:
    """Streamlit ke UploadedFile ka stand-in — sirf .file_id chahiye
    (dekhein session_helpers.is_new_diagnosis_upload docstring)."""

    def __init__(self, file_id):
        self.file_id = file_id


class TestIsNewDiagnosisUpload:
    """Build-order item 5 (Aug 2026), v0. Regression protection isi
    CLASS ke bug ke against jo "Change name" mein tha (16 Aug 2026) —
    Streamlit poora script rerun karta hai har interaction par,
    st.file_uploader SAME file object return karta rehta hai jab tak
    widget change na ho. Is check ke bina, koi bhi unrelated rerun
    dobara (billed) API call + duplicate DB row bana deta."""

    def test_no_file_uploaded_yet(self):
        turn = {}
        assert is_new_diagnosis_upload(turn, None) is False

    def test_first_upload_for_this_turn_is_new(self):
        turn = {}  # 'diag_processed_file_id' key abhi exist hi nahi karti
        uploaded = _FakeUploadedFile(file_id="abc123")
        assert is_new_diagnosis_upload(turn, uploaded) is True

    def test_same_file_on_a_later_rerun_is_not_new(self):
        # Ye asal scenario hai jo bug tha: student ne upload kiya, phir
        # kahin aur click kiya (jaise sidebar toggle) — poora script
        # rerun hua, st.file_uploader ne WAHI file object phir se
        # return kiya. Is file ko dobara process NAHI hona chahiye.
        turn = {"diag_processed_file_id": "abc123"}
        same_upload_again = _FakeUploadedFile(file_id="abc123")
        assert is_new_diagnosis_upload(turn, same_upload_again) is False

    def test_a_genuinely_different_file_is_new(self):
        # Student ne photo blurry thi, dobara/nayi photo upload ki —
        # ye GENUINELY process honi chahiye
        turn = {"diag_processed_file_id": "abc123"}
        new_upload = _FakeUploadedFile(file_id="xyz789")
        assert is_new_diagnosis_upload(turn, new_upload) is True