import io
import json
import logging
import os

from groq import Groq
from manga_ocr import MangaOcr
from PIL import Image

from kioku.models import CardItem

logger = logging.getLogger(__name__)

_mocr = MangaOcr()


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0].strip()
    return cleaned


def extract_cards(image_bytes: bytes, mime_type: str) -> list[CardItem]:
    """OCR with Manga OCR, then enrich with a single Groq call."""
    # --- OCR via Manga OCR (local, no API call) ---
    image = Image.open(io.BytesIO(image_bytes))
    ocr_text = _mocr(image)

    if not ocr_text or not ocr_text.strip():
        raise RuntimeError("Manga OCR returned no text.")

    logger.info("Manga OCR text: %s", ocr_text)

    # --- Enrich via Groq (1 API call) ---
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    model = os.environ.get("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct").strip()

    if not api_key:
        raise RuntimeError("GROQ_API_KEY is required.")

    client = Groq(api_key=api_key)

    prompt = (
        "I will give you Japanese text extracted from an image via OCR. "
        "For each sentence or phrase, produce:\n"
        "1. One entry for the complete sentence/phrase.\n"
        "2. One entry for each individual vocabulary word in that sentence. "
        "Only include content words (nouns, verbs, adjectives, adverbs). "
        "Do NOT include particles (は、が、を、に、で、と、の、も、へ、から、まで、より、か、よ、ね、な、けど、ば、て、たり), "
        "conjunctions, or punctuation.\n\n"
        "Return a JSON array. Each entry must have exactly these fields:\n"
        '- "japanese": the text (full sentence OR single word)\n'
        '- "reading": full hiragana reading\n'
        '- "meaning": English meaning (for sentences give the overall meaning, for words give the dictionary meaning)\n'
        '- "example_sentence": for sentences use the sentence itself; '
        "for words use the sentence it came from; "
        "for standalone words that didn't come from a sentence, create a natural example sentence using the word\n"
        '- "example_translation": English translation of the example_sentence\n\n'
        "IMPORTANT: Every field must be filled in. Never leave any field empty. "
        "Even if the text is incomplete or partial, provide your best translation.\n\n"
        "Return ONLY valid JSON. No other text.\n\n"
        f"OCR text:\n{ocr_text}"
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a JSON API. Return only valid JSON.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    content = (response.choices[0].message.content or "").strip()
    logger.info("Groq raw response: %s", content)
    text = _strip_code_fences(content)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as err:
        raise RuntimeError(f"Groq returned invalid JSON: {err}\nRaw: {content}") from err

    if not isinstance(parsed, list):
        raise RuntimeError(f"Groq returned non-list JSON: {content}")

    cards: list[CardItem] = []
    seen: set[str] = set()
    for obj in parsed:
        if not isinstance(obj, dict):
            continue

        jp = str(obj.get("japanese", "")).strip()
        if not jp or jp in seen:
            continue

        reading = str(obj.get("reading", "")).strip()
        meaning = str(obj.get("meaning", "")).strip()
        example_sentence = str(obj.get("example_sentence", "")).strip() or jp
        example_translation = str(obj.get("example_translation", "")).strip()

        if not reading:
            continue

        seen.add(jp)
        cards.append(
            CardItem(
                japanese=jp,
                reading=reading,
                meaning=meaning,
                example_sentence=example_sentence,
                example_translation=example_translation,
            )
        )

    if not cards:
        raise RuntimeError(
            f"No valid cards extracted.\n"
            f"OCR text: {ocr_text}\n"
            f"Groq response: {content}"
        )

    return cards
