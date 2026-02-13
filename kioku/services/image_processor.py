import io
import json
import logging
import os

import pytesseract
from groq import Groq
from PIL import Image

from kioku.models import CardItem

logger = logging.getLogger(__name__)


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0].strip()
    return cleaned


def enrich_text(text: str) -> list[CardItem]:
    """Translate English text into Japanese with readings, meanings, and examples via Groq."""
    if not text or not text.strip():
        raise RuntimeError("No text provided for enrichment.")

    logger.info("Enriching text: %s", text)

    # --- Enrich via Groq (1 API call) ---
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    model = os.environ.get("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct").strip()

    if not api_key:
        raise RuntimeError("GROQ_API_KEY is required.")

    client = Groq(api_key=api_key)

    prompt = (
        "I will give you English text. "
        "For each sentence or phrase, produce:\n"
        "1. One entry for the complete sentence/phrase translated into Japanese.\n"
        "2. One entry for each individual vocabulary word in that sentence translated into Japanese. "
        "Only include content words (nouns, verbs, adjectives, adverbs). "
        "Do NOT include articles, prepositions, conjunctions, or punctuation.\n\n"
        "Return a JSON array. Each entry must have exactly these fields:\n"
        '- "japanese": the Japanese translation (full sentence OR single word in kanji/kana)\n'
        '- "meaning": the original English text (for sentences give the full English sentence, for words give the English dictionary meaning)\n'
        '- "example_sentence": a natural English example sentence using the word or phrase\n'
        '- "example_translation": Japanese translation of the example_sentence\n\n'
        "IMPORTANT: Every field must be filled in. Never leave any field empty. "
        "Even if the text is incomplete or partial, provide your best translation.\n\n"
        "Return ONLY valid JSON. No other text.\n\n"
        f"English text:\n{text}"
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
    clean_text = _strip_code_fences(content)

    try:
        parsed = json.loads(clean_text)
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

        meaning = str(obj.get("meaning", "")).strip()
        example_sentence = str(obj.get("example_sentence", "")).strip() or jp
        example_translation = str(obj.get("example_translation", "")).strip()

        if not meaning:
            continue

        seen.add(jp)
        cards.append(
            CardItem(
                japanese=jp,
                meaning=meaning,
                example_sentence=example_sentence,
                example_translation=example_translation,
            )
        )

    if not cards:
        raise RuntimeError(
            f"No valid cards extracted.\n"
            f"Input text: {text}\n"
            f"Groq response: {content}"
        )

    return cards


def extract_cards(image_bytes: bytes, mime_type: str) -> list[CardItem]:
    """OCR with pytesseract, then enrich with a single Groq call."""
    # --- OCR via pytesseract (local, no API call) ---
    image = Image.open(io.BytesIO(image_bytes))
    ocr_text = pytesseract.image_to_string(image, lang="eng")

    if not ocr_text or not ocr_text.strip():
        raise RuntimeError("OCR returned no text.")

    logger.info("OCR text: %s", ocr_text)

    # Delegate to enrich_text
    return enrich_text(ocr_text)
