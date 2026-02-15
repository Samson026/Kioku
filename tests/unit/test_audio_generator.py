"""Unit tests for audio_generator service."""

import pytest
from unittest.mock import Mock

import httpx

from kioku.services.audio_generator import generate_audio


class TestGenerateAudio:
    """Tests for generate_audio function."""

    @pytest.mark.asyncio
    async def test_generate_audio_success(self, mock_voicevox):
        """Test successful audio generation."""
        text = "こんにちは"
        audio = await generate_audio(text)

        assert isinstance(audio, bytes)
        assert len(audio) > 0
        assert audio == b"mock_wav_audio_data"

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
    async def test_generate_audio_voicevox_connection_failure(self, monkeypatch):
        """Test audio generation handles VOICEVOX connection failures."""

        class MockAsyncClientFail:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, url, **kwargs):
                raise httpx.ConnectError("Connection refused")

        monkeypatch.setattr("httpx.AsyncClient", MockAsyncClientFail)

        with pytest.raises(RuntimeError, match="VOICEVOX request failed"):
            await generate_audio("こんにちは")

    @pytest.mark.asyncio
    async def test_generate_audio_voicevox_http_error(self, monkeypatch):
        """Test audio generation handles VOICEVOX HTTP errors."""

        class MockResponse:
            status_code = 500

            def raise_for_status(self):
                raise httpx.HTTPStatusError(
                    "Server error",
                    request=Mock(),
                    response=self
                )

        class MockAsyncClientError:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, url, **kwargs):
                return MockResponse()

        monkeypatch.setattr("httpx.AsyncClient", MockAsyncClientError)

        with pytest.raises(RuntimeError, match="VOICEVOX API error"):
            await generate_audio("こんにちは")

    @pytest.mark.asyncio
    async def test_generate_audio_no_audio_bytes(self, monkeypatch):
        """Test audio generation when VOICEVOX returns empty audio."""

        class MockResponse:
            content = b""
            status_code = 200

            def json(self):
                return {"query": "mock"}

            def raise_for_status(self):
                pass

        class MockAsyncClientEmpty:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, url, **kwargs):
                return MockResponse()

        monkeypatch.setattr("httpx.AsyncClient", MockAsyncClientEmpty)

        with pytest.raises(RuntimeError, match="VOICEVOX returned no audio"):
            await generate_audio("こんにちは")

    @pytest.mark.asyncio
    async def test_generate_audio_two_step_process(self, monkeypatch):
        """Test that audio generation performs both query and synthesis steps."""

        post_calls = []

        class MockResponse:
            def __init__(self, is_query):
                self.is_query = is_query
                self.status_code = 200

            @property
            def content(self):
                return b"wav_data"

            def json(self):
                return {"audioQuery": "data"}

            def raise_for_status(self):
                pass

        class MockAsyncClientTracking:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, url, **kwargs):
                post_calls.append({"url": url, "kwargs": kwargs})
                is_query = "audio_query" in url
                return MockResponse(is_query=is_query)

        monkeypatch.setattr("httpx.AsyncClient", MockAsyncClientTracking)

        await generate_audio("テスト")

        # Verify two POST requests were made
        assert len(post_calls) == 2
        assert "audio_query" in post_calls[0]["url"]
        assert "synthesis" in post_calls[1]["url"]
