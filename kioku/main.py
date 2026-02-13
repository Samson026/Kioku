import asyncio
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from groq import AuthenticationError, APIError

from kioku.models import ExtractionResult, GenerateRequest, TextExtractionRequest
from kioku.services.anki_builder import add_cards, sync_anki
from kioku.services.audio_generator import generate_audio
from kioku.services.image_processor import enrich_text, extract_cards

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/extract", response_model=ExtractionResult)
async def api_extract(file: UploadFile = File(...)):
    try:
        image_bytes = await file.read()
        mime_type = file.content_type or "image/jpeg"
        cards = extract_cards(image_bytes, mime_type)
        return ExtractionResult(cards=cards)
    except AuthenticationError as err:
        raise HTTPException(
            status_code=401,
            detail="GROQ_API_KEY is invalid or not set. Please check your .env file.",
        ) from err
    except APIError as err:
        raise HTTPException(status_code=502, detail=f"Groq API error: {err}") from err
    except RuntimeError as err:
        raise HTTPException(status_code=500, detail=str(err)) from err


@app.post("/api/extract-text", response_model=ExtractionResult)
async def api_extract_text(req: TextExtractionRequest):
    try:
        cards = enrich_text(req.text)
        return ExtractionResult(cards=cards)
    except AuthenticationError as err:
        raise HTTPException(
            status_code=401,
            detail="GROQ_API_KEY is invalid or not set. Please check your .env file.",
        ) from err
    except APIError as err:
        raise HTTPException(status_code=502, detail=f"Groq API error: {err}") from err
    except RuntimeError as err:
        raise HTTPException(status_code=500, detail=str(err)) from err


@app.post("/api/generate")
async def api_generate(req: GenerateRequest):
    try:
        # Collect unique texts to avoid duplicate TTS requests.
        unique_texts: dict[str, None] = {}
        for card in req.cards:
            unique_texts[card.meaning] = None
            unique_texts[card.example_sentence] = None

        text_list = list(unique_texts)
        audio_results = await asyncio.gather(
            *(generate_audio(t) for t in text_list)
        )
        audio_cache = dict(zip(text_list, audio_results))

        audio_map: dict[str, bytes] = {}
        for i, card in enumerate(req.cards):
            audio_map[f"word_{i}.mp3"] = audio_cache[card.meaning]
            audio_map[f"sentence_{i}.mp3"] = audio_cache[card.example_sentence]

        added = add_cards(req.cards, audio_map, req.deck_name)

        # Trigger sync with AnkiWeb after adding cards
        try:
            sync_anki()
        except RuntimeError:
            # Sync failed, but cards were added successfully
            pass

        return {"added": added}
    except RuntimeError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err


_static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("kioku.main:app", host="0.0.0.0", port=8000, reload=True)
