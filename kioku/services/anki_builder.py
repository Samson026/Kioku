import base64
import json
import os
import urllib.request

from kioku.models import CardItem, KanjiCard
from kioku.utils import audio_filename

DEFAULT_ANKI_CONNECT_URL = "http://localhost:8765"
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

KANJI_MODEL_NAME = "Japanese Kanji (ankiGen)"
KANJI_FRONT_TEMPLATE = '<div style="font-size:96px;text-align:center;">{{Kanji}}</div>'
KANJI_BACK_TEMPLATE = (
    '{{FrontSide}}<hr id="answer">'
    '<div style="text-align:center;margin:8px 0;">'
    '<span style="color:#888;font-size:14px;">On\'yomi: </span>'
    '<span style="font-size:20px;">{{Onyomi}}</span></div>'
    '<div style="text-align:center;margin:8px 0;">'
    '<span style="color:#888;font-size:14px;">Kun\'yomi: </span>'
    '<span style="font-size:20px;">{{Kunyomi}}</span></div>'
    '<div style="font-size:24px;text-align:center;margin:10px 0;">{{Meaning}}</div>'
    '<div style="text-align:center;margin-top:15px;font-size:18px;">'
    "<b>{{ExampleWord}}</b> ({{ExampleWordReading}})</div>"
)


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


def _ensure_kanji_model(model_name: str):
    """Create the kanji note type if it doesn't already exist."""
    existing = _anki_request("modelNames")
    if model_name in existing:
        return
    _anki_request(
        "createModel",
        modelName=model_name,
        inOrderFields=[
            "Kanji",
            "Onyomi",
            "Kunyomi",
            "Meaning",
            "ExampleWord",
            "ExampleWordReading",
        ],
        css=MODEL_CSS,
        cardTemplates=[
            {
                "Name": "Card 1",
                "Front": KANJI_FRONT_TEMPLATE,
                "Back": KANJI_BACK_TEMPLATE,
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
    for card in cards:
        word_audio_file = audio_filename(card.japanese, "word")
        sentence_audio_file = audio_filename(card.example_sentence, "sentence")

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


def add_kanji_cards(cards: list[KanjiCard], deck_name: str = "ankiGen") -> int:
    """Push kanji cards into Anki via AnkiConnect. Returns count of cards added."""
    _ensure_deck(deck_name)
    _ensure_kanji_model(KANJI_MODEL_NAME)

    added = 0
    for card in cards:
        _anki_request(
            "addNote",
            note={
                "deckName": deck_name,
                "modelName": KANJI_MODEL_NAME,
                "fields": {
                    "Kanji": card.kanji,
                    "Onyomi": card.onyomi,
                    "Kunyomi": card.kunyomi,
                    "Meaning": card.meaning,
                    "ExampleWord": card.example_word,
                    "ExampleWordReading": card.example_word_reading,
                },
                "options": {"allowDuplicate": False},
                "tags": ["ankiGen", "kanji"],
            },
        )
        added += 1

    return added
