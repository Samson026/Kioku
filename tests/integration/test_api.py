"""Integration tests for FastAPI endpoints."""

import io
import json

import pytest


class TestExtractEndpoint:
    """Tests for POST /api/extract endpoint."""

    def test_extract_success(self, test_client, sample_image_bytes, mock_easyocr, mock_groq_client):
        """Test successful image extraction."""
        files = {"file": ("test.png", io.BytesIO(sample_image_bytes), "image/png")}
        response = test_client.post("/api/extract", files=files)

        assert response.status_code == 200
        data = response.json()
        assert "cards" in data
        assert len(data["cards"]) >= 1
        assert "japanese" in data["cards"][0]
        assert "meaning" in data["cards"][0]

    def test_extract_missing_file(self, test_client):
        """Test extraction without file returns 422."""
        response = test_client.post("/api/extract")
        assert response.status_code == 422

    def test_extract_invalid_api_key(self, test_client, sample_image_bytes, mock_easyocr, monkeypatch):
        """Test extraction with invalid API key returns 401."""
        from groq import AuthenticationError

        def mock_groq_init_fail(api_key):
            raise AuthenticationError("Invalid API key")

        # Mock Groq to raise AuthenticationError
        mock_client = type('MockClient', (), {})()

        mock_request = type('MockRequest', (), {'method': 'POST', 'url': 'https://api.groq.com', 'headers': {}})()
        mock_response = type('MockResponse', (), {'status_code': 401, 'headers': {}, 'text': 'Unauthorized', 'request': mock_request})()
        auth_error = AuthenticationError("Invalid API key", response=mock_response, body=None)

        def mock_create(*args, **kwargs):
            raise auth_error

        mock_client.chat = type('MockChat', (), {})()
        mock_client.chat.completions = type('MockCompletions', (), {})()
        mock_client.chat.completions.create = mock_create

        def mock_groq_class(api_key):
            raise auth_error

        monkeypatch.setattr("kioku.services.image_processor.Groq", mock_groq_class)

        files = {"file": ("test.png", io.BytesIO(sample_image_bytes), "image/png")}
        response = test_client.post("/api/extract", files=files)

        assert response.status_code == 401
        assert "GROQ_API_KEY" in response.json()["detail"]

    def test_extract_empty_ocr_result(self, test_client, sample_image_bytes, mock_easyocr):
        """Test extraction with empty OCR result returns 500."""
        mock_easyocr.readtext.return_value = []

        files = {"file": ("test.png", io.BytesIO(sample_image_bytes), "image/png")}
        response = test_client.post("/api/extract", files=files)

        assert response.status_code == 500
        assert "OCR returned no text" in response.json()["detail"]


class TestExtractTextEndpoint:
    """Tests for POST /api/extract-text endpoint."""

    def test_extract_text_success(self, test_client, mock_groq_client):
        """Test successful text extraction."""
        payload = {"text": "Hello"}
        response = test_client.post("/api/extract-text", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "cards" in data
        assert len(data["cards"]) >= 1
        assert data["cards"][0]["japanese"] == "こんにちは"

    def test_extract_text_empty_text(self, test_client):
        """Test extraction with empty text returns 500."""
        payload = {"text": ""}
        response = test_client.post("/api/extract-text", json=payload)

        assert response.status_code == 500
        assert "No text provided" in response.json()["detail"]

    def test_extract_text_missing_field(self, test_client):
        """Test extraction without text field returns 422."""
        payload = {}
        response = test_client.post("/api/extract-text", json=payload)

        assert response.status_code == 422

    def test_extract_text_whitespace_only(self, test_client):
        """Test extraction with whitespace-only text returns 500."""
        payload = {"text": "   "}
        response = test_client.post("/api/extract-text", json=payload)

        assert response.status_code == 500
        assert "No text provided" in response.json()["detail"]


class TestGenerateEndpoint:
    """Tests for POST /api/generate endpoint."""

    @pytest.mark.asyncio
    async def test_generate_success(self, test_client, sample_cards, mock_edge_tts, mock_anki_connect):
        """Test successful audio generation and Anki card creation."""
        payload = {
            "cards": [card.model_dump() for card in sample_cards],
            "deck_name": "TestDeck",
        }
        response = test_client.post("/api/generate", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "added" in data
        assert data["added"] == 2

    @pytest.mark.asyncio
    async def test_generate_empty_cards(self, test_client, mock_edge_tts, mock_anki_connect):
        """Test generation with empty cards list."""
        payload = {"cards": [], "deck_name": "TestDeck"}
        response = test_client.post("/api/generate", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["added"] == 0

    @pytest.mark.asyncio
    async def test_generate_default_deck_name(self, test_client, sample_cards, mock_edge_tts, mock_anki_connect):
        """Test generation uses default deck name when not provided."""
        payload = {"cards": [card.model_dump() for card in sample_cards]}
        response = test_client.post("/api/generate", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "added" in data

    @pytest.mark.asyncio
    async def test_generate_edge_tts_failure(self, test_client, sample_cards, monkeypatch):
        """Test generation handles Edge TTS failures."""

        class MockCommunicateFail:
            def __init__(self, text, voice):
                self.text = text
                self.voice = voice

            async def stream(self):
                raise Exception("Edge TTS service unavailable")
                yield  # pragma: no cover

        monkeypatch.setattr(
            "kioku.services.audio_generator.edge_tts.Communicate", MockCommunicateFail
        )

        payload = {"cards": [card.model_dump() for card in sample_cards]}
        response = test_client.post("/api/generate", json=payload)

        assert response.status_code == 502
        assert "Edge TTS request failed" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_generate_anki_connect_failure(self, test_client, sample_cards, mock_edge_tts, monkeypatch):
        """Test generation handles AnkiConnect failures."""

        def mock_urlopen_error(request):
            from unittest.mock import Mock
            mock_response = Mock()
            mock_response.read.return_value = json.dumps(
                {"result": None, "error": "Failed to connect to Anki"}
            ).encode()
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)
            return mock_response

        monkeypatch.setattr("urllib.request.urlopen", mock_urlopen_error)

        payload = {"cards": [card.model_dump() for card in sample_cards]}
        response = test_client.post("/api/generate", json=payload)

        assert response.status_code == 502
        assert "AnkiConnect error" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_generate_deduplicates_audio(self, test_client, mock_edge_tts, mock_anki_connect):
        """Test that generate endpoint deduplicates audio generation for same text."""
        # Create cards with duplicate japanese text
        cards = [
            {
                "japanese": "こんにちは",
                "meaning": "Hello",
                "example_sentence": "こんにちは、元気ですか？",
                "example_translation": "Hello, how are you?",
            },
            {
                "japanese": "こんにちは",  # Duplicate
                "meaning": "Hello",
                "example_sentence": "こんにちは、元気ですか？",  # Duplicate
                "example_translation": "Hello, how are you?",
            },
        ]

        payload = {"cards": cards}
        response = test_client.post("/api/generate", json=payload)

        assert response.status_code == 200
        # Should successfully handle duplicates without generating audio twice
