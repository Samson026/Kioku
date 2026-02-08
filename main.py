import asyncio

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from models import ExtractionResult, GenerateRequest
from services.anki_builder import add_cards
from services.audio_generator import generate_audio
from services.image_processor import extract_cards

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
    image_bytes = await file.read()
    mime_type = file.content_type or "image/jpeg"
    cards = extract_cards(image_bytes, mime_type)
    return ExtractionResult(cards=cards)


@app.post("/api/generate")
async def api_generate(req: GenerateRequest):
    try:
        # Collect unique texts to avoid duplicate TTS requests.
        unique_texts: dict[str, None] = {}
        for card in req.cards:
            unique_texts[card.japanese] = None
            unique_texts[card.example_sentence] = None

        text_list = list(unique_texts)
        audio_results = await asyncio.gather(
            *(generate_audio(t) for t in text_list)
        )
        audio_cache = dict(zip(text_list, audio_results))

        audio_map: dict[str, bytes] = {}
        for i, card in enumerate(req.cards):
            audio_map[f"word_{i}.mp3"] = audio_cache[card.japanese]
            audio_map[f"sentence_{i}.mp3"] = audio_cache[card.example_sentence]

        added = add_cards(req.cards, audio_map, req.deck_name)
        return {"added": added}
    except RuntimeError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err


app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
