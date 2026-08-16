from session_helpers import reset_identity


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