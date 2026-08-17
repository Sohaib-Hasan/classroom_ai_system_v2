"""
image_helpers.py
--------------------
Chhote, pure image-processing helpers jo app.py mein use hote hain —
`session_helpers.py` jaisa hi pattern: Streamlit-independent, isliye
plain pytest se test ho sakte hain (app.py khud ek top-level Streamlit
script hai — dekhein session_helpers.py docstring).
"""

from __future__ import annotations

import io

from PIL import Image


def resize_image_for_upload(file_like, max_width=1600, jpeg_quality=80):
    """Build-order item 5 (Aug 2026), v0 — diagnosis-mode photo uploads.
    Student phone photos kaafi bade ho sakte hain (10+ MB) — hume sirf
    itni resolution chahiye ke handwriting parhi ja sake; upload/token
    cost ke liye chhota rakhte hain (dekhein plan doc Section 5).

    `file_like`: koi bhi file-like object jo PIL.Image.open() accept
    kare (Streamlit ka UploadedFile, ya test mein io.BytesIO).
    Return: (jpeg_bytes, mime_type)."""
    img = Image.open(file_like).convert("RGB")  # PNG transparency JPEG mein save nahi hoti
    if img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, int(img.height * ratio)))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=jpeg_quality)
    return buf.getvalue(), "image/jpeg"