import base64
import json
import os

from groq import Groq

from models import CardItem


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0].strip()
    return cleaned


def extract_cards(image_bytes: bytes, mime_type: str) -> list[CardItem]:
    """Extract and enrich Japanese cards in a single Groq Vision call."""
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    vision_model = os.environ.get(
        "GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"
    ).strip()

    if not api_key:
        raise RuntimeError("GROQ_API_KEY is required.")

    b64_image = base64.b64encode(image_bytes).decode()
    client = Groq(api_key=api_key)

    prompt = (
        "Extract ALL Japanese text from this image. "
        "For each sentence or phrase you find, produce:\n"
        "1. One entry for the complete sentence/phrase.\n"
        "2. One entry for each individual vocabulary word in that sentence. "
        "Only include content words (nouns, verbs, adjectives, adverbs). "
        "Do NOT include particles (は、が、を、に、で、と、の、も、へ、から、まで、より、か、よ、ね、な、けど、ば、て、たり), "
        "conjunctions, or punctuation.\n\n"
        "Return a JSON array. Each entry must have exactly these fields:\n"
        '- "japanese": the text (full sentence OR single word)\n'
        '- "reading": hiragana reading\n'
        '- "meaning": English meaning\n'
        '- "example_sentence": for sentences use the sentence itself; '
        "for words use the sentence it came from\n"
        '- "example_translation": English translation of the example_sentence\n\n'
        "Return ONLY valid JSON. No other text."
    )

    response = client.chat.completions.create(
        model=vision_model,
        messages=[
            {
                "role": "system",
                "content": "You are a JSON API. Return only valid JSON.",
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{b64_image}",
                        },
                    },
                ],
            },
        ],
        temperature=0.2,
    )

    content = (response.choices[0].message.content or "").strip()
    text = _strip_code_fences(content)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as err:
        raise RuntimeError(f"Groq returned invalid JSON: {err}") from err

    if not isinstance(parsed, list):
        raise RuntimeError("Groq returned non-list JSON.")

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
        example_sentence = str(obj.get("example_sentence", "")).strip()
        example_translation = str(obj.get("example_translation", "")).strip()

        if not all([reading, meaning, example_sentence, example_translation]):
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
        raise RuntimeError("No valid cards extracted from image.")

    return cards
