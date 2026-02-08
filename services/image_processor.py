import json
import os

from google import genai
from google.genai import types

from models import CardItem

PROMPT = """Analyze this image of Japanese text. Extract all distinct vocabulary items, phrases, or sentences.
For each item return a JSON array with objects containing:
- japanese: the text in Japanese (kanji/kana as written)
- reading: hiragana reading
- meaning: English translation
- example_sentence: a simple example sentence using this word
- example_translation: English translation of the example

Return ONLY the JSON array, no other text."""


def extract_cards(image_bytes: bytes, mime_type: str) -> list[CardItem]:
    """Extract Japanese vocabulary from an image using Gemini Vision."""
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            PROMPT,
        ],
    )

    text = response.text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0].strip()

    items = json.loads(text)
    return [CardItem(**item) for item in items]
