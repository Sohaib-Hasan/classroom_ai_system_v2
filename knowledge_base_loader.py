"""
knowledge_base_loader.py
---------------------------
knowledge_base.json load karta hai.
Agar file Git LFS pointer ho, missing ho, ya invalid JSON ho to
GitHub Release se download karta hai (LFS quota se bachne ke liye).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import requests
import streamlit as st

# Default Release URL — apna actual release URL yahan daal dena
DEFAULT_KB_URL = (
    "https://github.com/Sohaib-Hasan/classroom_ai_system_v2/"
    "releases/download/kb-v1/knowledge_base.json"
)

def _is_lfs_pointer(path: Path) -> bool:
    """File Git LFS pointer text hai ya nahi check karta hai."""
    try:
        if path.stat().st_size > 1024:  # real file 100MB+ hoti hai
            return False
        head = path.read_text(encoding="utf-8", errors="ignore")[:200]
        return head.startswith("version https://git-lfs.github.com/spec/v1")
    except Exception:
        return False

def _download_kb(url: str, dest: Path) -> None:
    """Release se knowledge_base.json download karta hai."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):  # 1 MB
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
    if total and downloaded < total * 0.9:
        raise RuntimeError(
            f"Download incomplete: got {downloaded} bytes, expected ~{total}"
        )

@st.cache_resource
def load_knowledge_base(path: str = "knowledge_base.json"):
    kb_path = Path(path)

    # Optional: Streamlit Secrets se custom URL le sakte ho
    try:
        kb_url = st.secrets.get("KNOWLEDGE_BASE_URL", DEFAULT_KB_URL)
    except Exception:
        kb_url = DEFAULT_KB_URL

    need_download = (
        not kb_path.exists()
        or _is_lfs_pointer(kb_path)
        or kb_path.stat().st_size < 1_000_000  # < 1 MB → almost certainly pointer/corrupt
    )

    if need_download:
        st.info(
            "📦 Knowledge base missing / LFS pointer detected. "
            "Downloading full file from GitHub Release (one-time, ~111 MB)..."
        )
        try:
            _download_kb(kb_url, kb_path)
            st.success("✅ Knowledge base downloaded successfully.")
        except Exception as e:
            raise RuntimeError(
                f"Could not download knowledge_base.json from:\n{kb_url}\n\n"
                f"Error: {e}\n\n"
                "Fix options:\n"
                "1. Upload knowledge_base.json to a GitHub Release and set the correct URL\n"
                "   (or set KNOWLEDGE_BASE_URL in Streamlit Secrets).\n"
                "2. Or buy a small Git LFS data pack so the pointer resolves correctly."
            ) from e

    # Ab real JSON load karo
    try:
        with open(kb_path, "r", encoding="utf-8") as f:
            kb = json.load(f)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"'{path}' valid JSON nahi hai. "
            "Probably still an LFS pointer or corrupt download. "
            f"Original error: {e}"
        ) from e

    if not kb:
        raise ValueError(
            f"'{path}' khali hai — pehle `python3 embed_chunks.py` chala kar "
            "knowledge base banayein, phir use GitHub Release pe upload karein."
        )

    embeddings_matrix = np.array([item["embedding"] for item in kb])
    courses = sorted(set(c["course"] for c in kb))
    return kb, embeddings_matrix, courses