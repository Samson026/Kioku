import edge_tts

VOICE = "ja-JP-NanamiNeural"


async def generate_audio(text: str) -> bytes:
    """Generate MP3 audio for Japanese text using Microsoft Edge TTS."""
    if not text or not text.strip():
        raise RuntimeError("Cannot generate audio for empty text.")

    communicate = edge_tts.Communicate(text=text, voice=VOICE)
    audio_chunks: list[bytes] = []

    try:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])
    except Exception as err:
        raise RuntimeError(f"Edge TTS request failed: {err}") from err

    if not audio_chunks:
        raise RuntimeError(f"Edge TTS returned no audio for: {text!r}")

    return b"".join(audio_chunks)
