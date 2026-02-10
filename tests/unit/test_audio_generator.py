"""Unit tests for audio_generator service."""

import pytest

from kioku.services.audio_generator import generate_audio


class TestGenerateAudio:
    """Tests for generate_audio function."""

    @pytest.mark.asyncio
    async def test_generate_audio_success(self, mock_edge_tts):
        """Test successful audio generation."""
        text = "こんにちは"
        audio = await generate_audio(text)

        assert isinstance(audio, bytes)
        assert len(audio) > 0
        assert audio == b"mock_audio_chunk_1mock_audio_chunk_2"

    @pytest.mark.asyncio
    async def test_generate_audio_empty_text(self):
        """Test audio generation with empty text raises error."""
        with pytest.raises(RuntimeError, match="Cannot generate audio for empty text"):
            await generate_audio("")

    @pytest.mark.asyncio
    async def test_generate_audio_whitespace_only(self):
        """Test audio generation with whitespace-only text raises error."""
        with pytest.raises(RuntimeError, match="Cannot generate audio for empty text"):
            await generate_audio("   ")

    @pytest.mark.asyncio
    async def test_generate_audio_edge_tts_failure(self, monkeypatch):
        """Test audio generation handles Edge TTS failures."""

        class MockCommunicateFail:
            def __init__(self, text, voice):
                self.text = text
                self.voice = voice

            async def stream(self):
                raise Exception("Edge TTS service unavailable")
                # This line is unreachable but needed for generator syntax
                yield  # pragma: no cover

        monkeypatch.setattr(
            "kioku.services.audio_generator.edge_tts.Communicate", MockCommunicateFail
        )

        with pytest.raises(RuntimeError, match="Edge TTS request failed"):
            await generate_audio("こんにちは")

    @pytest.mark.asyncio
    async def test_generate_audio_no_audio_chunks(self, monkeypatch):
        """Test audio generation when Edge TTS returns no audio chunks."""

        class MockCommunicateEmpty:
            def __init__(self, text, voice):
                self.text = text
                self.voice = voice

            async def stream(self):
                # Return only non-audio chunks
                yield {"type": "metadata", "data": "some metadata"}

        monkeypatch.setattr(
            "kioku.services.audio_generator.edge_tts.Communicate", MockCommunicateEmpty
        )

        with pytest.raises(RuntimeError, match="Edge TTS returned no audio"):
            await generate_audio("こんにちは")

    @pytest.mark.asyncio
    async def test_generate_audio_filters_non_audio_chunks(self, monkeypatch):
        """Test audio generation filters out non-audio chunks."""

        class MockCommunicateMixed:
            def __init__(self, text, voice):
                self.text = text
                self.voice = voice

            async def stream(self):
                yield {"type": "metadata", "data": "metadata"}
                yield {"type": "audio", "data": b"chunk1"}
                yield {"type": "other", "data": "other"}
                yield {"type": "audio", "data": b"chunk2"}

        monkeypatch.setattr(
            "kioku.services.audio_generator.edge_tts.Communicate", MockCommunicateMixed
        )

        audio = await generate_audio("こんにちは")
        assert audio == b"chunk1chunk2"
