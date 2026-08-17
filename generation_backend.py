"""
generation_backend.py
------------------------
embedding_backend.py ki tarah, is module ka maqsad hai GENERATION provider
ko bhi "pluggable" banana — taake:

  1. Default/recommended path Gemini rahe (native structured-output support,
     free tier, aur ab tak jo bhi testing hui hai wo isi par hui hai).
  2. Agar kabhi Gemini ka free-tier quota khatam ho jaye (jaise exam week
     mein bhari traffic ke doran), ek FALLBACK provider switch-on kiya ja
     sake — jaise AgentRouter (agentrouter.org) — bina app.py ka code
     chhede.

IMPORTANT — AgentRouter (ya koi bhi third-party "gateway") ke baare mein:
  - Ye ek unverified, non-profit third-party proxy hai jo aapki requests
    asal model provider (Anthropic/OpenAI/etc.) tak forward karta hai.
    Iski koi published privacy/data-retention policy maujood nahi — student
    sawal-jawab is gateway se guzrenge, jo aapke direct control mein nahi.
  - Isse "primary/only" backbone na banayein — sirf FALLBACK ke tor par
    use karein jab Gemini quota khatam ho jaye. Isliye is file mein
    GENERATION_PROVIDER = "gemini" hi default hai.
  - Maine (Claude) is integration ko sandbox ki network restrictions ki
    wajah se live test NAHI kar saka (agentrouter.org allowed domains
    mein nahi tha) — sirf OpenAI-compatible /v1/chat/completions ke
    standard, well-documented contract ke mutabiq likha hai. Deploy karne
    se PEHLE khud ek chhota manual test zaroor karein:
        python3 verify_fallback_provider.py
  - Apni key kabhi bhi chat mein ya code mein hardcode karke commit na
    karein — sirf config.py (gitignored) ya Streamlit Secrets mein.
"""

from __future__ import annotations

import abc
import base64
import json
import re
import time
from typing import Type, TypeVar

from pydantic import BaseModel

from core import repair_json_escaping

T = TypeVar("T", bound=BaseModel)


class GenerationBackend(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def generate(self, system_instruction: str, prompt: str, response_schema: Type[T]) -> T:
        """Ek structured (pydantic-validated) jawab generate karta hai."""


def _strip_markdown_fences(text: str) -> str:
    """Kuch models (khaaskar non-OpenAI models jo OpenAI-compatible gateway
    ke peeche hain) JSON-mode maangne ke bawajood ```json ... ``` fences
    mein wrap kar dete hain — isse defensively hata dete hain."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


class GeminiGenerationBackend(GenerationBackend):
    """Default/recommended — Gemini ki Interactions API, native JSON-schema
    structured output ke saath."""

    name = "gemini"

    def __init__(self, client=None, clients=None, model: str = "gemini-3.6-flash"):
        # FIX (quota-scaling): dekhein embedding_backend.py mein wahi
        # comment — yahan bhi 'client' (purana) aur 'clients' (naya,
        # rotation ke liye list) dono chalte hain.
        if clients:
            self._clients = list(clients)
        elif client is not None:
            self._clients = [client]
        else:
            raise ValueError("GeminiGenerationBackend ke liye 'client' ya 'clients' chahiye.")
        self._model = model

    def generate(self, system_instruction: str, prompt: str, response_schema: Type[T]) -> T:
        last_error = None
        # FIX (quota-scaling): agar ek key ka quota khatam ho jaye, agli
        # key try hoti hai — sirf tab error dikhta hai jab SAB keys fail
        # ho jayein.
        for client in self._clients:
            try:
                interaction = client.interactions.create(
                    model=self._model,
                    system_instruction=system_instruction,
                    input=prompt,
                    # FIX: Gemini docs ke mutabiq response_format ek list honi
                    # chahiye jismein {"type","mime_type","schema"} keys hon —
                    # pehle raw schema seedha pass ho rahi thi.
                    response_format=self._response_format(response_schema),
                )
                return self._parse_response(interaction, response_schema)
            except Exception as e:  # noqa: BLE001 — agli client try karni hai
                last_error = e
        raise last_error

    def generate_from_image(
        self, system_instruction: str, prompt: str, image_bytes: bytes,
        mime_type: str, response_schema: Type[T],
    ) -> T:
        """Build-order item 4 (Aug 2026) — image-input capability SPIKE.
        `generate()` jaisa hi hai (same client-rotation, same response
        parsing), bas `input` ab text + image dono wala list hai.

        Design decisions (dekhein plan doc Section 5):
        - Inline base64 image data, Files API upload NAHI — student
          phone-photo jaisi chhoti, ek-baar-use hone wali image ke liye
          Files API overkill hai (extra roundtrip, file-lifecycle
          manage karna). Format Gemini Interactions API ke current
          (verified Aug 2026) docs ke mutabiq: {"type": "image",
          "data": <base64 str>, "mime_type": ...}.
        - Ye method sirf GeminiGenerationBackend par hai, base
          GenerationBackend abstract class ka hissa NAHI —
          OpenAICompatibleGenerationBackend (fallback provider) image
          input support nahi karta, aur ye jaan-boojh kar scope ke
          bahar rakha hai (dekhein plan doc: diagnosis mode fallback
          provider use hi nahi karega, primary Gemini fail ho to clear
          "abhi unavailable hai" message dikhayega, poora system down
          nahi hoga).
        - Resize/compress karna is method ka kaam NAHI hai — caller
          (jab diagnosis-mode UI banega) upload se pehle image compress
          kare (max ~1600px width, jpeg quality ~80) — yahan bas jo
          bytes diye jayein wahi bhejta hai.

        >>> SPIKE RESULT (confirmed 16 Aug 2026, live test by Sohaib):
        >>> response_format (structured JSON output) DOES combine
        >>> reliably with multimodal input — a real handwritten-notes
        >>> photo was sent, and the model returned accurate structured
        >>> JSON (description matched real page content: epsilon-N
        >>> notation, convergent/divergent sequences — not a generic/
        >>> hallucinated answer). Spike closed; safe to build build-order
        >>> item 5 (diagnosis v0) on top of this. See CHANGELOG.md."""
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        last_error = None
        for client in self._clients:
            try:
                interaction = client.interactions.create(
                    model=self._model,
                    system_instruction=system_instruction,
                    input=[
                        {"type": "text", "text": prompt},
                        {"type": "image", "data": image_b64, "mime_type": mime_type},
                    ],
                    response_format=self._response_format(response_schema),
                )
                return self._parse_response(interaction, response_schema)
            except Exception as e:  # noqa: BLE001
                last_error = e
        raise last_error

    @staticmethod
    def _response_format(response_schema: Type[T]):
        return [
            {
                "type": "text",
                "mime_type": "application/json",
                "schema": response_schema.model_json_schema(),
            }
        ]

    @staticmethod
    def _parse_response(interaction, response_schema: Type[T]) -> T:
        # FIX (production bug, Aug 2026): Gemini kabhi LaTeX commands
        # (\times, \buildrel, waghera) mein backslash double-escape
        # karna bhool jata hai — is se jawab corrupt ho jata hai (kabhi
        # silently, kabhi crash ke saath). Parse karne se pehle repair
        # karte hain — dekhein core.repair_json_escaping().
        repaired_text = repair_json_escaping(interaction.output_text)
        return response_schema.model_validate_json(repaired_text)


class OpenAICompatibleGenerationBackend(GenerationBackend):
    """Kisi bhi OpenAI-Chat-Completions-compatible gateway ke liye — jaise
    AgentRouter (agentrouter.org/v1), ya kal ko OpenRouter/Groq bhi isi
    class se chal jayenge, bas base_url/model badalna hoga.

    NOTE: har underlying model strict JSON-schema enforcement support
    nahi karta (ye AgentRouter jaisi gateway ke peeche 30+ alag models
    ho sakte hain) — isliye hum widely-supported "JSON mode"
    (`response_format: {"type": "json_object"}`) use karte hain, aur
    schema ko system-instruction mein explicitly bhi likh dete hain taake
    model ko poori tarah pata ho kya chahiye. Agar phir bhi parsing fail
    ho (kabhi kabhi kisi model se markdown-fenced JSON aa jata hai), ek
    retry try karte hain."""

    name = "openai_compatible"

    def __init__(self, api_key: str, base_url: str, model: str, timeout: float = 40, retries: int = 2):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._retries = retries

    def generate(self, system_instruction: str, prompt: str, response_schema: Type[T]) -> T:
        import requests  # lazy import — sirf tab chahiye jab ye backend use ho

        schema = response_schema.model_json_schema()
        full_system = (
            f"{system_instruction}\n\n"
            "You MUST reply with ONLY a single valid JSON object matching this "
            "JSON Schema, and nothing else — no markdown code fences, no "
            f"commentary before or after:\n{json.dumps(schema)}"
        )

        last_error = None
        for attempt in range(self._retries):
            try:
                resp = requests.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "messages": [
                            {"role": "system", "content": full_system},
                            {"role": "user", "content": prompt},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.2,
                    },
                    timeout=self._timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                content = _strip_markdown_fences(content)
                # FIX (production bug, Aug 2026): same LaTeX-backslash
                # escaping issue can happen with any underlying model —
                # dekhein core.repair_json_escaping().
                content = repair_json_escaping(content)
                return response_schema.model_validate_json(content)
            except Exception as e:  # noqa: BLE001
                last_error = e
                if attempt < self._retries - 1:
                    time.sleep(2)
        raise last_error


# Known OpenAI-compatible gateways — base_url shortcuts taake config.py
# mein poora URL yaad na rakhna pade. Agar koi aur gateway use karna ho,
# GENERATION_PROVIDER="openai_compatible" ke saath GENERATION_BASE_URL
# seedha config.py mein de sakte hain.
KNOWN_GATEWAYS = {
    "agentrouter": "https://agentrouter.org/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "groq": "https://api.groq.com/openai/v1",
}


def get_generation_backend(provider: str, **kwargs) -> GenerationBackend:
    provider = (provider or "gemini").lower().strip()
    if provider == "gemini":
        return GeminiGenerationBackend(
            client=kwargs.get("client"),
            clients=kwargs.get("clients"),
            model=kwargs.get("model", "gemini-3.6-flash"),
        )

    base_url = kwargs.get("base_url") or KNOWN_GATEWAYS.get(provider)
    if base_url is None:
        raise ValueError(
            f"Unknown provider {provider!r} — ya to 'gemini', ya "
            f"{list(KNOWN_GATEWAYS)} mein se ek, ya 'openai_compatible' "
            "(base_url khud dein)."
        )
    if "api_key" not in kwargs or not kwargs["api_key"]:
        raise ValueError(f"{provider} ke liye api_key chahiye (config.py mein set karein).")
    if "model" not in kwargs or not kwargs["model"]:
        raise ValueError(
            f"{provider} ke liye model naam chahiye — apne AgentRouter console "
            "mein dekh kar config.py mein GENERATION_MODEL_FALLBACK set karein "
            "(e.g. 'claude-sonnet-4-5-20250929' ya 'gpt-4o-mini')."
        )
    return OpenAICompatibleGenerationBackend(api_key=kwargs["api_key"], base_url=base_url, model=kwargs["model"])