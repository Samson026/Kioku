# Kioku (Anki Card Generator)

Generate Japanese Anki cards from an image:
- Extract vocabulary with Gemini Vision
- Generate Japanese audio with Edge TTS
- Push notes directly into Anki via AnkiConnect

## Requirements

- Python 3.11+
- Anki desktop app
- AnkiConnect add-on enabled in Anki
- Gemini API key (used for image/text extraction)

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

### 1. Gemini API key

Create `.env` in the project root:

```env
GEMINI_API_KEY=your_key_here
```

### 2. AnkiConnect URL

Optional `config.json` in project root:

```json
{
  "anki_connect_url": "http://127.0.0.1:8765"
}
```

Notes:
- `anki_connect_url` is used by the Anki integration.
- Gemini API key is read from `.env` / environment only.

## Run

### CLI entrypoint (installed via `setup.py`)

```bash
anki-card-generator
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

- Gemini quota/rate issues on extraction
  - This affects `/api/extract` only.
  - Retry later or use a key/project with higher limits.

## Development Notes

- Frontend is a Vue 3 app embedded in `static/index.html` (CDN-based, no separate build step).
- Backend is FastAPI in `main.py`.
- Services:
  - `services/image_processor.py`
  - `services/audio_generator.py`
  - `services/anki_builder.py`
