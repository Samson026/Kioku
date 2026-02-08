# Kioku

Generate Japanese Anki cards from an image:
- Extract Japanese text with Manga OCR
- Enrich reading/meaning/example fields with Groq
- Generate Japanese audio with Edge TTS
- Push notes directly into Anki via AnkiConnect

## Requirements

- Python 3.11+
- Anki desktop app with AnkiConnect add-on enabled

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configuration

Set the following in `.env`:

- `GROQ_API_KEY` (required)
- `GROQ_MODEL` (optional, default: `meta-llama/llama-4-scout-17b-16e-instruct`)
- `ANKI_CONNECT_URL` (optional, default: `http://172.20.144.1:8765`)

## Run

```bash
kioku
```

### Docker

```bash
docker build -t kioku .
docker run --env-file .env -p 8000:8000 kioku
```

App runs at `http://localhost:8000`.

## API Endpoints

- `POST /api/extract` — multipart form with `file`, returns extracted card objects
- `POST /api/generate` — JSON body with `cards` and optional `deck_name`, generates audio and pushes notes to Anki

## Project Structure

```
kioku/
├── __init__.py
├── __main__.py        # CLI entrypoint
├── main.py            # FastAPI app
├── models.py          # Pydantic models
└── services/
    ├── image_processor.py   # Manga OCR + Groq enrichment
    ├── audio_generator.py   # Edge TTS
    └── anki_builder.py      # AnkiConnect integration
static/
└── index.html         # Vue 3 frontend
```
