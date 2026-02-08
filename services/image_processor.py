import json
import os
import re

import easyocr
from groq import Groq
from janome.tokenizer import Tokenizer

from models import CardItem

# Keep only strings that contain at least one Japanese character.
JAPANESE_CHAR_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]")
# Split likely sentence boundaries while keeping phrase chunks.
SPLIT_RE = re.compile(r"[、。・,.;!?！？\n\r\t]+")
# Keep tokens containing one or more Japanese chars.
WORD_CHAR_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]+")

_reader = easyocr.Reader(["ja"], gpu=False)
_tokenizer = Tokenizer()


def _should_ignore_particles() -> bool:
    return os.environ.get("IGNORE_PARTICLES", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0].strip()
    return cleaned


def _normalize_text(text: str) -> str:
    # Remove spaces inserted by OCR between Japanese characters.
    collapsed = re.sub(
        r"(?<=[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff])\s+(?=[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff])",
        "",
        text,
    )
    return collapsed.strip()


def _build_raw_cards(image_bytes: bytes) -> list[CardItem]:
    # Use paragraph mode to avoid character-by-character fragmentation.
    ocr_lines = _reader.readtext(image_bytes, detail=0, paragraph=True)
    ignore_particles = _should_ignore_particles()
    seen: set[str] = set()
    items: list[CardItem] = []

    for line in ocr_lines:
        normalized_line = _normalize_text(line)
        if not normalized_line:
            continue

        # Split large lines on punctuation so cards are closer to words/phrases.
        segments = [seg.strip() for seg in SPLIT_RE.split(normalized_line) if seg.strip()]
        for segment in segments:
            if not JAPANESE_CHAR_RE.search(segment):
                continue

            # 1) Add a card for the full sentence/phrase.
            if segment not in seen:
                seen.add(segment)
                items.append(
                    CardItem(
                        japanese=segment,
                        reading="",
                        meaning="",
                        example_sentence=segment,
                        example_translation="",
                    )
                )

            # 2) Add a card for each word inside that sentence.
            for token in _tokenizer.tokenize(segment):
                surface = token.surface.strip()
                if not surface:
                    continue

                pos = token.part_of_speech.split(",")[0]
                if pos == "記号":
                    continue
                if ignore_particles and pos == "助詞":
                    continue
                if not WORD_CHAR_RE.fullmatch(surface):
                    continue
                if surface in seen:
                    continue

                seen.add(surface)
                items.append(
                    CardItem(
                        japanese=surface,
                        reading="",
                        meaning="",
                        example_sentence=segment,
                        example_translation="",
                    )
                )

    return items


def _enrich_with_groq(cards: list[CardItem]) -> list[CardItem]:
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    model = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant").strip()

    if not cards:
        return cards
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is required for card enrichment.")
    if not model:
        raise RuntimeError("GROQ_MODEL is empty.")

    prompt = (
        "For each Japanese input item, return JSON array entries with fields: "
        "japanese, reading, meaning, example_sentence, example_translation. "
        "Rules: keep japanese exactly identical to input text, reading must be hiragana, "
        "meaning and example_translation in English, example_sentence should be natural and short. "
        "Do not omit items. Return JSON only."
    )
    inputs = [card.japanese for card in cards]
    messages = [
        {
            "role": "system",
            "content": "You are a JSON API. Return only valid JSON.",
        },
        {
            "role": "user",
            "content": f"{prompt}\n\nInputs:\n{json.dumps(inputs, ensure_ascii=False)}",
        },
    ]

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,
        )
        content = (response.choices[0].message.content or "").strip()
        text = _strip_code_fences(content)
        parsed = json.loads(text)
    except Exception as err:
        raise RuntimeError(f"Groq enrichment failed: {err}") from err

    if not isinstance(parsed, list):
        raise RuntimeError("Groq enrichment returned non-list JSON.")

    # Some models may return extra objects; match strictly by japanese text.
    parsed_by_japanese: dict[str, dict] = {}
    for i, obj in enumerate(parsed):
        if not isinstance(obj, dict):
            continue
        jp = str(obj.get("japanese", "")).strip()
        if not jp:
            continue
        if jp not in parsed_by_japanese:
            parsed_by_japanese[jp] = obj

    enriched_map: dict[str, CardItem] = {}
    missing: list[CardItem] = []
    for base in cards:
        obj = parsed_by_japanese.get(base.japanese)
        if obj is None:
            missing.append(base)
            continue

        reading = str(obj.get("reading", "")).strip()
        meaning = str(obj.get("meaning", "")).strip()
        example_sentence = str(obj.get("example_sentence", "")).strip()
        example_translation = str(obj.get("example_translation", "")).strip()

        if not all([reading, meaning, example_sentence, example_translation]):
            missing.append(base)
            continue

        enriched_map[base.japanese] = CardItem(
            japanese=base.japanese,
            reading=reading,
            meaning=meaning,
            example_sentence=example_sentence,
            example_translation=example_translation,
        )

    # Second pass: request only missing items one-by-one for robustness.
    for base in missing:
        enriched_map[base.japanese] = _enrich_single_with_groq(client, model, base)

    still_missing = [card.japanese for card in cards if card.japanese not in enriched_map]
    if still_missing:
        missing_preview = ", ".join(still_missing[:5])
        raise RuntimeError(
            "Groq enrichment missing or incomplete fields for extracted items: "
            f"{missing_preview}"
        )

    return [enriched_map[card.japanese] for card in cards]


def _enrich_single_with_groq(client: Groq, model: str, base: CardItem) -> CardItem:
    prompt = (
        "Return exactly one JSON object with fields: "
        "japanese, reading, meaning, example_sentence, example_translation. "
        "Rules: japanese must exactly equal the provided input text, reading in hiragana, "
        "meaning and example_translation in English, example_sentence short and natural. "
        "Return JSON only."
    )
    messages = [
        {"role": "system", "content": "You are a JSON API. Return only valid JSON."},
        {
            "role": "user",
            "content": f"{prompt}\n\nInput:\n{json.dumps(base.japanese, ensure_ascii=False)}",
        },
    ]
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,
        )
        content = (response.choices[0].message.content or "").strip()
        text = _strip_code_fences(content)
        obj = json.loads(text)
    except Exception as err:
        raise RuntimeError(f"Groq single-item enrichment failed for '{base.japanese}': {err}") from err

    if not isinstance(obj, dict):
        raise RuntimeError(f"Groq single-item enrichment returned non-object for '{base.japanese}'.")

    reading = str(obj.get("reading", "")).strip()
    meaning = str(obj.get("meaning", "")).strip()
    example_sentence = str(obj.get("example_sentence", "")).strip()
    example_translation = str(obj.get("example_translation", "")).strip()
    if not all([reading, meaning, example_sentence, example_translation]):
        raise RuntimeError(f"Groq single-item enrichment missing fields for '{base.japanese}'.")

    return CardItem(
        japanese=base.japanese,
        reading=reading,
        meaning=meaning,
        example_sentence=example_sentence,
        example_translation=example_translation,
    )


def extract_cards(image_bytes: bytes, mime_type: str) -> list[CardItem]:
    """Extract Japanese text with EasyOCR/Janome and enrich via Groq."""
    del mime_type  # Unused with EasyOCR.

    raw_cards = _build_raw_cards(image_bytes)
    return _enrich_with_groq(raw_cards)
