import io
import wave

from google import genai
from google.genai import types

import config


def generate_audio(text: str) -> bytes:
    """Generate WAV audio for Japanese text using Gemini TTS. Returns WAV bytes."""
    client = genai.Client(api_key=config.get_gemini_api_key())

    response = client.models.generate_content(
        model="gemini-2.5-flash-preview-tts",
        contents=f"Read the following Japanese text aloud: {text}",
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Kore",
                    )
                )
            ),
        ),
    )

    candidate = response.candidates[0] if response.candidates else None
    if not candidate or not candidate.content or not candidate.content.parts:
        raise RuntimeError(f"TTS returned no audio for: {text!r}")

    pcm_data = candidate.content.parts[0].inline_data.data

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(pcm_data)

    return buf.getvalue()
