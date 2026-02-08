# Kioku (Anki Card Generator)

Generate Japanese Anki cards from an image:
- Extract Japanese text with EasyOCR + Janome
- Enrich reading/meaning/example fields with Groq
- Generate Japanese audio with Edge TTS
- Push notes directly into Anki via AnkiConnect

## Requirements

- Python 3.11+
- Anki desktop app
- AnkiConnect add-on enabled in Anki

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Or install dependencies directly:

```bash
pip install -r requirements.txt
```

## Configuration

### AnkiConnect URL

Optional `config.json` in project root:

```json
{
  "anki_connect_url": "http://127.0.0.1:8765"
}
```

Notes:
- `anki_connect_url` is used by the Anki integration.
- Set `GROQ_API_KEY` in `.env` (required for extraction enrichment).
- Optional: set `GROQ_MODEL` (default is `llama-3.1-8b-instant`).
- Optional: set `IGNORE_PARTICLES=true|false` (default `true`) to skip/include Japanese particles in word cards.

## Run

### CLI entrypoint (installed via `setup.py`)

```bash
kioku
```

### Direct Python run

```bash
python main.py
```

App default URL:
- `http://localhost:8000`

## API Endpoints

- `POST /api/extract`
  - multipart form with `file`
  - returns extracted card objects
- `POST /api/generate`
  - JSON body with `cards` and optional `deck_name`
  - generates audio and pushes notes to Anki

## Troubleshooting

- `Connection refused` on `/api/generate`
  - AnkiConnect is not reachable at configured `anki_connect_url`.
  - Ensure Anki is open and AnkiConnect is installed/enabled.

- Slow first OCR call
  - EasyOCR loads models on first use, so the first extraction can take longer.

## Development Notes

- Frontend is a Vue 3 app embedded in `static/index.html` (CDN-based, no separate build step).
- Backend is FastAPI in `main.py`.
- Services:
  - `services/image_processor.py`
  - `services/audio_generator.py`
  - `services/anki_builder.py`
