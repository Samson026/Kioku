import base64
import json
import urllib.request

import config
from models import CardItem
MODEL_NAME = "Japanese Vocab (ankiGen)"

FRONT_TEMPLATE = (
    '<div style="font-size:48px;text-align:center;">{{Japanese}}</div>'
    "<div>{{WordAudio}}</div>"
)
BACK_TEMPLATE = (
    '{{FrontSide}}<hr id="answer">'
    '<div style="font-size:24px;text-align:center;color:#666;">{{Reading}}</div>'
    '<div style="font-size:28px;text-align:center;margin:10px 0;">{{Meaning}}</div>'
    '<div style="font-size:20px;margin-top:15px;">'
    "<b>Example:</b> {{ExampleSentence}}<br>"
    "<i>{{ExampleTranslation}}</i>"
    "</div>"
    "<div>{{SentenceAudio}}</div>"
)
MODEL_CSS = ".card { font-family: 'Noto Sans JP', sans-serif; padding: 20px; }"


def _anki_request(action: str, **params):
    """Send a request to AnkiConnect and return the result."""
    payload = json.dumps({"action": action, "version": 6, "params": params}).encode()
    req = urllib.request.Request(config.get_anki_connect_url(), data=payload)
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
            "Reading",
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


def add_cards(
    cards: list[CardItem],
    audio_map: dict[str, bytes],
    deck_name: str = "ankiGen",
) -> int:
    """Push cards into Anki via AnkiConnect. Returns count of cards added."""
    _ensure_deck(deck_name)
    _ensure_model(MODEL_NAME)

    # Store all audio files
    for filename, audio_bytes in audio_map.items():
        _anki_request(
            "storeMediaFile",
            filename=filename,
            data=base64.b64encode(audio_bytes).decode(),
        )

    # Add notes
    added = 0
    for i, card in enumerate(cards):
        word_audio_file = f"{card.japanese}_word.mp3"
        sentence_audio_file = f"{card.japanese}_sentence_{i}.mp3"

        _anki_request(
            "addNote",
            note={
                "deckName": deck_name,
                "modelName": MODEL_NAME,
                "fields": {
                    "Japanese": card.japanese,
                    "Reading": card.reading,
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
