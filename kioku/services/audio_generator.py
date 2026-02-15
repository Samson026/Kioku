import os

import httpx

DEFAULT_VOICEVOX_URL = "http://localhost:50021"
DEFAULT_VOICEVOX_SPEAKER = "0"


async def generate_audio(text: str) -> bytes:
    """Generate WAV audio for Japanese text using VOICEVOX."""
    if not text or not text.strip():
        raise RuntimeError("Cannot generate audio for empty text.")

    base_url = os.environ.get("VOICEVOX_URL", DEFAULT_VOICEVOX_URL).rstrip("/")
    speaker = os.environ.get("VOICEVOX_SPEAKER", DEFAULT_VOICEVOX_SPEAKER)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: Get audio query
            query_response = await client.post(
                f"{base_url}/audio_query",
                params={"text": text, "speaker": speaker},
            )
            query_response.raise_for_status()
            audio_query = query_response.json()

            # Step 2: Synthesize audio
            synthesis_response = await client.post(
                f"{base_url}/synthesis",
                params={"speaker": speaker},
                json=audio_query,
            )
            synthesis_response.raise_for_status()
            audio_bytes = synthesis_response.content

    except httpx.HTTPStatusError as err:
        raise RuntimeError(
            f"VOICEVOX API error (status {err.response.status_code}): {err}"
        ) from err
    except httpx.RequestError as err:
        raise RuntimeError(
            f"VOICEVOX request failed. Is VOICEVOX running at {base_url}? Error: {err}"
        ) from err
    except Exception as err:
        raise RuntimeError(f"VOICEVOX audio generation failed: {err}") from err

    if not audio_bytes:
        raise RuntimeError(f"VOICEVOX returned no audio for: {text!r}")

    return audio_bytes
