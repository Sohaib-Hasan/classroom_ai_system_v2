"""
session_helpers.py
---------------------
Chhote, pure session-state helpers jo app.py mein use hote hain — is
alag file mein isliye rakhe hain taake plain pytest se test ho sakein.
`app.py` khud ek top-level Streamlit script hai: PIN gate, `st.secrets`
access, waghera sab module-IMPORT hote hi chal jate hain (Streamlit ka
apna execution model hai) — isliye `app.py` ko seedha `import` karke
test karna fragile/impossible hai bina ek poori Streamlit runtime
context ke. Chhoti, Streamlit-independent logic yahan rakhne se woh
normal pytest se, bina kisi mocking overhead ke, test ho sakti hai.

`session_state` parameter koi bhi dict-like object le sakta hai —
Streamlit ka asli `st.session_state` (jo attribute- AUR dict-style
access dono support karta hai), ya test mein ek plain `dict`.
"""

from __future__ import annotations


def reset_identity(session_state) -> None:
    """"Not you? Change name" button ka logic.

    FIX (mentor ne 16 Aug 2026 ko catch kiya): pehle sirf `student_id`
    clear hota tha, `messages` (chat history) nahi. Matlab shared/lab
    computer scenario mein — jiske liye ye button bana tha — Student A
    poochta, "Change name" dabata, Student B apna naam likhta, lekin
    Student B ko Student A ki poori purani chat screen par dikhti
    rehti thi jab tak course na badle ya "Start a new topic" na
    dabaya jaye. Database-level logging sahi thi (naya sawaal sahi
    student_id ke sath log hota), lekin ye ek UI-level privacy leak
    thi jo button ka poora point hi undermine kar rahi thi.

    Ab dono clear karta hai — naya student ek khaali chat se shuru
    karta hai.
    """
    session_state["student_id"] = None
    session_state["messages"] = []


def is_new_diagnosis_upload(turn, uploaded_file) -> bool:
    """Build-order item 5 (Aug 2026), v0. `st.file_uploader` poora
    Streamlit script rerun hone ke bawajood SAME file object return
    karta rehta hai jab tak widget clear/change na ho — bina is check
    ke, koi bhi UNRELATED click app mein kahin bhi ek nayi (billed)
    diagnosis API call AUR ek duplicate DB log row bana deta, usi
    upload ke liye baar baar (isi CLASS ka bug jo "Change name" mein
    tha, dekhein reset_identity docstring aur CHANGELOG 16 Aug 2026).

    `turn`: dict jisme is turn ka last-processed file id store hota hai
    (`diag_processed_file_id` key). `uploaded_file`: Streamlit
    UploadedFile jaisa koi bhi object jiska `.file_id` attribute ho
    (ya test mein ek simple stand-in).
    """
    if uploaded_file is None:
        return False
    return turn.get("diag_processed_file_id") != uploaded_file.file_id