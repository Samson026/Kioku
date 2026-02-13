import importlib
import json
import logging
import os

from groq import Groq

from kioku.models import CardItem

logger = logging.getLogger(__name__)
_EASYOCR_READER = None


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _is_sentence_like(text: str) -> bool:
    value = str(text or "").strip()
    if not value:
        return False
    if any(ch in value for ch in ".!?;:"):
        return True
    return len(value.split()) >= 3


def _finalize_cards(cards: list[CardItem], source_text: str) -> list[CardItem]:
    source = source_text.strip()
    source_norm = _normalize_text(source)
    sentence_card: CardItem | None = None

    if source_norm:
        for card in cards:
            if _normalize_text(card.meaning) == source_norm:
                sentence_card = card
                break

    if sentence_card is None and cards and source_norm:
        source_words = set(source_norm.split())
        best_score = -1.0
        best_card: CardItem | None = None
        for card in cards:
            meaning_norm = _normalize_text(card.meaning)
            if not meaning_norm:
                continue

            if not _is_sentence_like(card.meaning):
                continue

            overlap = 0
            meaning_words = meaning_norm.split()
            if meaning_words:
                overlap = sum(1 for word in meaning_words if word in source_words)

            score = 0.0
            if meaning_norm in source_norm:
                score += 2.0
            score += overlap / max(len(meaning_words), 1)
            if _is_sentence_like(card.meaning):
                score += 1.0

            if score > best_score:
                best_score = score
                best_card = card

        if best_card is not None and best_score > 0:
            sentence_card = best_card

    if sentence_card is None and cards and source:
        best_japanese = max(cards, key=lambda c: len(c.japanese)).japanese
        sentence_card = CardItem(
            japanese=best_japanese,
            meaning=source,
            example_sentence=source,
            example_translation=best_japanese,
        )
        cards = [sentence_card, *cards]
    elif sentence_card is not None:
        sentence_card = CardItem(
            japanese=sentence_card.japanese,
            meaning=sentence_card.meaning,
            example_sentence=sentence_card.meaning,
            example_translation=sentence_card.japanese,
        )
        cards = [
            sentence_card if (c.japanese == sentence_card.japanese and c.meaning == sentence_card.meaning) else c
            for c in cards
        ]

    deduped: list[CardItem] = []
    seen: set[tuple[str, str]] = set()
    for card in cards:
        key = (card.japanese, card.meaning)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(card)

    deduped.sort(
        key=lambda c: 0 if _normalize_text(c.meaning) == _normalize_text(c.example_sentence) else 1
    )
    return deduped


def _get_easyocr_reader():
    global _EASYOCR_READER
    if _EASYOCR_READER is not None:
        return _EASYOCR_READER

    try:
        easyocr_module = importlib.import_module("easyocr")
    except ImportError as err:
        raise RuntimeError(
            "easyocr is not installed. Install project dependencies and retry."
        ) from err

    _EASYOCR_READER = easyocr_module.Reader(["en"], gpu=False)
    return _EASYOCR_READER


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
        "For the full sentence entry only: set example_sentence exactly equal to meaning, "
        "and example_translation exactly equal to japanese.\n\n"
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
    for obj in parsed:
        if not isinstance(obj, dict):
            continue

        jp = str(obj.get("japanese", "")).strip()
        if not jp:
            continue

        meaning = str(obj.get("meaning", "")).strip()
        example_sentence = str(obj.get("example_sentence", "")).strip() or meaning
        example_translation = str(obj.get("example_translation", "")).strip()

        if not meaning:
            continue

        cards.append(
            CardItem(
                japanese=jp,
                meaning=meaning,
                example_sentence=example_sentence,
                example_translation=example_translation,
            )
        )

    cards = _finalize_cards(cards, text)

    if not cards:
        raise RuntimeError(
            f"No valid cards extracted.\n"
            f"Input text: {text}\n"
            f"Groq response: {content}"
        )

    return cards


def extract_cards(image_bytes: bytes, mime_type: str) -> list[CardItem]:
    """OCR with easyocr, then enrich with a single Groq call."""
    # --- OCR via easyocr (local, no API call) ---
    ocr_reader = _get_easyocr_reader()
    ocr_lines = ocr_reader.readtext(image_bytes, detail=0, paragraph=True)
    ocr_text = "\n".join(str(line).strip() for line in ocr_lines if str(line).strip())

    if not ocr_text or not ocr_text.strip():
        raise RuntimeError("OCR returned no text.")

    logger.info("OCR text: %s", ocr_text)

    # Delegate to enrich_text
    return enrich_text(ocr_text)
