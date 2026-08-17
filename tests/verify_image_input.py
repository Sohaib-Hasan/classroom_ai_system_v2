"""
verify_image_input.py
------------------------
Ye ek MANUAL smoke-test hai — pytest suite ka hissa nahi (kyunke ye asli
internet aur asli Gemini API key maangta hai). Build-order item 4
(image-input SPIKE) ka poora point yehi test hai: `generate_from_image()`
sandbox mein mocked tests se sirf ye confirm hota hai ke hum sahi REQUEST
SHAPE bhej rahe hain (Gemini Interactions API ke documented contract ke
mutabiq) — ye asal mein reliably kaam karta hai ya nahi, khaaskar
structured JSON output (response_format) multimodal input ke saath
combine hone par, ye sirf ek live call se pata chalega. Maine (Claude)
ye is sandbox mein test NAHI kar saka — koi Google/Gemini domain allowed
domains list mein nahi hai.

Chalane se pehle:
    1. config.py mein GEMINI_API_KEY set hona chahiye (already hoga agar
       app.py chala rahe hain).

Chalana:
    python3 verify_image_input.py                  # synthetic test image use karega
    python3 verify_image_input.py /path/to/photo.jpg  # apni photo se test karein
                                                        # (jaise handwritten kaam ki
                                                        # asli photo — production
                                                        # scenario ke sabse qareeb)

Ye kya check karta hai:
    1. Kya call bilkul crash hue bina return karti hai (format Gemini ko
       samajh aata hai)?
    2. Kya response STRUCTURED JSON schema ke mutabiq parse hoti hai (ye
       wahi khula sawaal hai jo spike ne verify karna tha)?
    3. Kya model ne image ka content genuinely "dekha" — response mein
       kuch aisa hai jo sirf image dekh kar pata chal sakta hai (taake
       pakka ho ke image bhi ja rahi hai, sirf text prompt nahi)?
"""

import io
import sys

from config import GEMINI_API_KEY
from generation_backend import get_generation_backend
from pydantic import BaseModel


class ImageReadResult(BaseModel):
    description: str
    contains_math: bool


def _make_synthetic_test_image() -> bytes:
    """Koi photo na di ho to matplotlib se ek chhoti test-image banate
    hain — "2 + 2 = 4" jaisa simple text, taake bina kisi photo ke bhi
    turant chalaya ja sake. Production scenario (handwritten photo) ke
    liye asli image path dena zyada meaningful hai — dekhein docstring."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(4, 2))
    ax.text(0.5, 0.5, "2 + 2 = 4", fontsize=28, ha="center", va="center")
    ax.axis("off")
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def main():
    if not GEMINI_API_KEY:
        print("config.py mein GEMINI_API_KEY set nahi hai — kuch test karne ko nahi hai.")
        sys.exit(0)

    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        print(f"Testing with: {image_path}")
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        mime_type = "image/png" if image_path.lower().endswith(".png") else "image/jpeg"
    else:
        print("Koi image path nahi diya — synthetic test image bana raha hoon ('2 + 2 = 4').")
        image_bytes = _make_synthetic_test_image()
        mime_type = "image/png"

    # NOTE: get_generation_backend("gemini", ...) client= ya clients=
    # kwarg maangta hai, api_key= nahi — dekhein generation_backend.py.
    from google import genai
    backend = get_generation_backend("gemini", client=genai.Client(api_key=GEMINI_API_KEY))

    try:
        result = backend.generate_from_image(
            system_instruction=(
                "You are an assistant that describes images. Always reply with "
                "valid JSON matching the given schema."
            ),
            prompt="Describe what you see in this image in one sentence. Does it contain any math?",
            image_bytes=image_bytes,
            mime_type=mime_type,
            response_schema=ImageReadResult,
        )
        print("\n✅ Call succeeded AND response parsed as structured JSON.")
        print(f"   description: {result.description}")
        print(f"   contains_math: {result.contains_math}")
        print(
            "\nManually confirm: does 'description' actually describe THIS image "
            "(not a generic/hallucinated answer)? If yes — spike confirmed, image "
            "input + structured output work together. Safe to build build-order "
            "item 5 (diagnosis v0) on top of this."
        )
    except Exception as e:
        print(f"\n❌ Failed: {e!r}")
        print(
            "\nCommon causes:\n"
            "  - Model/SDK version doesn't support this input shape — re-check\n"
            "    current google-genai docs, the format may have changed\n"
            "  - response_format (structured output) may not combine reliably\n"
            "    with multimodal input — try again with response_schema removed\n"
            "    (call client.interactions.create directly) to isolate whether\n"
            "    the image part itself is the problem, or the combination is\n"
            "  - Image too large / wrong mime_type\n"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()