import base64
import hashlib
import json
import os
import re
import urllib.request

from kioku.models import CardItem

DEFAULT_ANKI_CONNECT_URL = "http://localhost:8765"
MODEL_NAME = "English-Japanese Vocab (ankiGen)"

FRONT_TEMPLATE = (
    '<div style="font-size:36px;text-align:center;">{{Meaning}}</div>'
)
BACK_TEMPLATE = (
    '{{FrontSide}}<hr id="answer">'
    '<div style="font-size:48px;text-align:center;">{{Japanese}}</div>'
    "<div>{{WordAudio}}</div>"
    '<div style="font-size:20px;margin-top:15px;">'
    "<b>Example:</b> {{ExampleSentence}}<br>"
    "<i>{{ExampleTranslation}}</i>"
    "</div>"
    "<div>{{SentenceAudio}}</div>"
)
MODEL_CSS = ".card { font-family: 'Noto Sans JP', sans-serif; padding: 20px; }"


def _audio_filename(kind: str, text: str) -> str:
    """Build a stable, text-based media filename to avoid index collisions."""
    normalized = " ".join(str(text or "").strip().split())
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    if not slug:
        slug = "empty"
    slug = slug[:40]
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:10]
    return f"{kind}_{slug}_{digest}.mp3"


def _anki_request(action: str, **params):
    """Send a request to AnkiConnect and return the result."""
    payload = json.dumps({"action": action, "version": 6, "params": params}).encode()
    url = os.environ.get("ANKI_CONNECT_URL", DEFAULT_ANKI_CONNECT_URL)
    req = urllib.request.Request(url, data=payload)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read())
    if body.get("error"):
        raise RuntimeError(f"AnkiConnect error: {body['error']}")
    return body.get("result")


def _ensure_model(model_name: str):
    """Create the note type if it doesn't already exist."""
    existing = _anki_request("modelNames")
    if model_name in existing:
        return
    _anki_request(
        "createModel",
        modelName=model_name,
        inOrderFields=[
            "Japanese",
            "Meaning",
            "ExampleSentence",
            "ExampleTranslation",
            "WordAudio",
            "SentenceAudio",
        ],
        css=MODEL_CSS,
        cardTemplates=[
            {
                "Name": "Card 1",
                "Front": FRONT_TEMPLATE,
                "Back": BACK_TEMPLATE,
            }
        ],
    )


def _ensure_deck(deck_name: str):
    """Create the deck (no-op if it already exists)."""
    _anki_request("createDeck", deck=deck_name)


def sync_anki():
    """Trigger AnkiConnect to sync with AnkiWeb."""
    _anki_request("sync")


def add_cards(
    cards: list[CardItem],
    audio_map: dict[str, bytes],
    deck_name: str = "ankiGen",
) -> int:
    """Push cards into Anki via AnkiConnect. Returns count of cards added.

    `audio_map` is keyed by source text (card.meaning / card.example_sentence).
    """
    _ensure_deck(deck_name)
    _ensure_model(MODEL_NAME)

    # Add notes
    added = 0
    stored_filenames: set[str] = set()
    for card in cards:
        word_audio_file = _audio_filename("word", card.meaning)
        sentence_audio_file = _audio_filename("sentence", card.example_sentence)

        word_audio_bytes = audio_map[card.meaning]
        sentence_audio_bytes = audio_map[card.example_sentence]

        if word_audio_file not in stored_filenames:
            _anki_request(
                "storeMediaFile",
                filename=word_audio_file,
                data=base64.b64encode(word_audio_bytes).decode(),
            )
            stored_filenames.add(word_audio_file)

        if sentence_audio_file not in stored_filenames:
            _anki_request(
                "storeMediaFile",
                filename=sentence_audio_file,
                data=base64.b64encode(sentence_audio_bytes).decode(),
            )
            stored_filenames.add(sentence_audio_file)

        _anki_request(
            "addNote",
            note={
                "deckName": deck_name,
                "modelName": MODEL_NAME,
                "fields": {
                    "Japanese": card.japanese,
                    "Meaning": card.meaning,
                    "ExampleSentence": card.example_sentence,
                    "ExampleTranslation": card.example_translation,
                    "WordAudio": f"[sound:{word_audio_file}]",
                    "SentenceAudio": f"[sound:{sentence_audio_file}]",
                },
                "options": {"allowDuplicate": False},
                "tags": ["ankiGen"],
            },
        )
        added += 1

    return added
