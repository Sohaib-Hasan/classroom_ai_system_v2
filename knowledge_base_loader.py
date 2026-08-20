"""
knowledge_base_loader.py
---------------------------
knowledge_base.json (embed_chunks.py se banti hai) ko load karta hai aur
embeddings ko ek numpy matrix mein convert karta hai — taake retrieval
(cosine similarity) fast ho.

Streamlit ke `@st.cache_resource` se wrap kiya gaya hai taake ye poore
app-process mein sirf EK BAAR load ho (94MB+ file har request pe dobara
parse karna bohat slow hota).

FIX (Aug 2026, deployment bug — "locally chalti hai, live nahi chalti"):
ye file 111MB+ ki hai — pehle Git LFS se track hoti thi. GitHub LFS ka
FREE tier sirf 1GB/month bandwidth deta hai, jo repeated deploys/
reboots se khatam ho sakta hai. Quota khatam hone par GitHub kabhi kabhi
silently sirf ek chhota LFS "pointer" text file serve karta hai
(~130 bytes: "version https://git-lfs.github.com/spec/v1\noid sha256:...
\nsize ..."), asli 111MB content nahi — matlab `json.load()` crash
karta hai (`Expecting value: line 1 column 1`), lekin sirf DEPLOYED
(Streamlit Cloud) environment mein, local machine par nahi (jahan file
already disk par thi, ya Git LFS pehle se sahi pull ho chuki thi).

Fix: file ab Git/LFS se poori tarah hata di gayi hai (dekhein
DEPLOYMENT_CHECKLIST.md). Ye loader ab GitHub Release se download karta
hai agar local file missing hai YA suspiciously choti hai (LFS pointer
jaisi) — Releases LFS bandwidth quota mein NAHI ginte, alag aur bade
(2GB tak per-file) hote hain, free.
"""

import json
import os

import numpy as np
import requests
import streamlit as st

# FIX: apna asli GitHub Release asset URL yahan daalein. Apne Release
# page par asset link par right-click → "Copy link address" — pattern
# hamesha ye hota hai:
#   https://github.com/<user>/<repo>/releases/download/<tag>/<filename>
KNOWLEDGE_BASE_URL = "https://github.com/Sohaib-Hasan/classroom_ai_system_v2/releases/download/kb-v1/knowledge_base.json"

# LFS pointer files ~130 bytes hoti hain, asli file 100MB+ — 1MB
# threshold in dono ke beech kaafi safe margin hai
_MIN_VALID_SIZE_BYTES = 1_000_000


def needs_download(path: str) -> bool:
    """Pure, Streamlit-independent — file missing hai ya LFS-pointer
    jaisi choti hai to True."""
    return not (os.path.exists(path) and os.path.getsize(path) >= _MIN_VALID_SIZE_BYTES)


def ensure_knowledge_base_present(path: str):
    """Pure, Streamlit-independent (isliye plain pytest se testable —
    dekhein session_helpers.py/image_helpers.py ka wahi pattern). Agar
    file missing hai ya LFS-pointer jaisi choti hai, GitHub Release se
    download karta hai. Local dev mein (jahan asli file already disk
    par hai) kuch nahi karta — bilkul pehle jaisa hi behavior."""
    if not needs_download(path):
        return

    if "REPLACE_WITH_YOUR_TAG" in KNOWLEDGE_BASE_URL:
        raise RuntimeError(
            f"'{path}' missing hai ya invalid hai (LFS pointer jaisa lag raha hai — "
            "size check fail hua), aur KNOWLEDGE_BASE_URL abhi placeholder hai "
            "knowledge_base_loader.py mein. Apna asli GitHub Release asset URL daalein."
        )

    resp = requests.get(KNOWLEDGE_BASE_URL, timeout=180, stream=True)
    resp.raise_for_status()
    tmp_path = path + ".downloading"
    with open(tmp_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)
    os.replace(tmp_path, path)  # atomic — beech mein crash hone se corrupt file nahi rahegi


@st.cache_resource
def load_knowledge_base(path: str = "knowledge_base.json"):
    if needs_download(path):
        with st.spinner("Downloading knowledge base (ek dafa hota hai, ~111MB, thodi der lagegi)..."):
            ensure_knowledge_base_present(path)
    with open(path, "r", encoding="utf-8") as f:
        kb = json.load(f)
    if not kb:
        raise ValueError(
            f"'{path}' khali hai ya load nahi hui — pehle `python3 embed_chunks.py` "
            "chala kar knowledge base banayein."
        )
    embeddings_matrix = np.array([item["embedding"] for item in kb])
    courses = sorted(set(c["course"] for c in kb))
    return kb, embeddings_matrix, courses
