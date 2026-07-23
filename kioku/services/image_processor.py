import io
import json
import logging
import os
import re

from anthropic import Anthropic
from manga_ocr import MangaOcr
from PIL import Image

from kioku.models import CardItem, KanjiCard
from kioku.constants import CLAUDE_MODEL

logger = logging.getLogger(__name__)

_mocr = MangaOcr()


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0].strip()
    return cleaned


def enrich_text(text: str) -> list[CardItem]:
    """Enrich Japanese text with readings, meanings, and examples via Claude."""
    if not text or not text.strip():
        raise RuntimeError("No text provided for enrichment.")

    logger.info("Enriching text: %s", text)

    # --- Enrich via Claude (1 API call) ---
    api_key = os.environ.get("CLAUDE_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError("CLAUDE_API_KEY is required.")

    client = Anthropic(api_key=api_key)

    system_prompt = """
        You process Japanese text into structured study entries.

        For each sentence or phrase, produce:
        1. One entry for the complete sentence or phrase.
        2. One entry for each individual vocabulary word in that sentence.

        For vocabulary entries, include only content words:
        - Nouns
        - Verbs
        - Adjectives
        - Adverbs

        Do not create entries for:
        - Particles, including は、が、を、に、で、と、の、も、へ、から、まで、より、か、よ、ね、な、けど、ば、て、たり
        - Conjunctions
        - Punctuation

        Return a JSON array. Every entry must contain exactly these fields:
        - "japanese": The complete sentence, phrase, or individual vocabulary word.
        - "reading": The full hiragana reading.
        - "meaning": The overall English meaning for sentences, or dictionary meaning for words.
        - "example_sentence": For sentence entries, use the original sentence. For word entries, use the sentence the word came from. For standalone words, create a natural Japanese example sentence.
        - "example_translation": The English translation of "example_sentence".

        Every field must be filled in. Never return an empty field.

        If the Japanese text is incomplete or fragmentary, provide the best possible interpretation and translation.

        Return only valid JSON. Do not include Markdown, code fences, explanations, or any other text.
    """.strip()

    response = client.messages.create(
        model=CLAUDE_MODEL,
        system=system_prompt,
        messages=[
            {"role": "user", "content": text},
        ],
        max_tokens=1024,
    )

    content = response.content[0].text
    logger.info("claude raw response: %s", content)
    clean_text = _strip_code_fences(content)

    try:
        parsed = json.loads(clean_text)
    except json.JSONDecodeError as err:
        raise RuntimeError(
            f"Claude returned invalid JSON: {err}\nRaw: {content}"
        ) from err

    if not isinstance(parsed, list):
        raise RuntimeError(f"Claude returned non-list JSON: {content}")

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
            f"No valid cards extracted.\nInput text: {text}\nClaude response: {content}"
        )

    return cards


def extract_kanji(text: str) -> list[KanjiCard]:
    """Extract unique kanji from text and return per-kanji info via Claude."""
    if not text or not text.strip():
        raise RuntimeError("No text provided for kanji extraction.")

    # Pre-extract unique kanji in order of appearance
    kanji_chars = list(dict.fromkeys(re.findall(r"[\u4e00-\u9fff]", text)))
    if not kanji_chars:
        return []

    api_key = os.environ.get("CLAUDE_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError("CLAUDE_API_KEY is required.")

    client = Anthropic(api_key=api_key)

    kanji_list_str = "、".join(kanji_chars)
    system_prompt = """
        You process kanji characters into structured study entries.

        Return a JSON array with one object for each requested kanji, preserving
        the requested order. Every object must contain exactly these fields:
        - "kanji": The single kanji character.
        - "onyomi": The on'yomi reading in katakana (for example, "ショク").
        - "kunyomi": The kun'yomi reading in hiragana (for example, "た.べる"), or an empty string if none exists.
        - "meaning": The primary English meaning.
        - "example_word": A common Japanese word using the kanji.
        - "example_word_reading": The hiragana reading of the example word.

        Return only valid JSON. Do not include Markdown, code fences,
        explanations, or any other text.
    """.strip()

    response = client.messages.create(
        model=CLAUDE_MODEL,
        system=system_prompt,
        messages=[
            {"role": "user", "content": kanji_list_str},
        ],
        max_tokens=1024,
    )

    content = response.content[0].text
    logger.info("Claude kanji response: %s", content)
    clean_text = _strip_code_fences(content)

    try:
        parsed = json.loads(clean_text)
    except json.JSONDecodeError as err:
        raise RuntimeError(
            f"Claude returned invalid JSON: {err}\nRaw: {content}"
        ) from err

    if not isinstance(parsed, list):
        raise RuntimeError(f"Claude returned non-list JSON: {content}")

    cards: list[KanjiCard] = []
    seen: set[str] = set()
    for obj in parsed:
        if not isinstance(obj, dict):
            continue
        kanji = str(obj.get("kanji", "")).strip()
        if not kanji or kanji in seen:
            continue
        seen.add(kanji)
        cards.append(
            KanjiCard(
                kanji=kanji,
                onyomi=str(obj.get("onyomi", "")).strip(),
                kunyomi=str(obj.get("kunyomi", "")).strip(),
                meaning=str(obj.get("meaning", "")).strip(),
                example_word=str(obj.get("example_word", "")).strip(),
                example_word_reading=str(obj.get("example_word_reading", "")).strip(),
            )
        )

    if not cards:
        raise RuntimeError(f"No kanji found in text: {text}")

    return cards


def extract_cards(image_bytes: bytes, mime_type: str) -> list[CardItem]:
    """OCR with Manga OCR, then enrich with a single Claude call."""
    # --- OCR via Manga OCR (local, no API call) ---
    image = Image.open(io.BytesIO(image_bytes))
    ocr_text = _mocr(image)

    if not ocr_text or not ocr_text.strip():
        raise RuntimeError("Manga OCR returned no text.")

    logger.info("Manga OCR text: %s", ocr_text)

    # Delegate to enrich_text
    return enrich_text(ocr_text)
